"""Toma de trabajos y perfilado de documentos.

El worker no decide nada financiero. Lee un fichero que **ya** salio de
cuarentena, calcula su forma y la guarda.

Toda la escritura sobre la cola pasa por dos funciones de base de datos. El rol
del worker no tiene UPDATE sobre `processing_run` ni ningun privilegio sobre
`dispatch_pointer`: lo que tiene es permiso para ejecutar `claim_next_run` y
`finish_run`, con parametros validados. Un worker comprometido puede pedir
trabajo y cerrar el suyo; no puede reescribir el estado de la cola.

Tres invariantes sostienen el protocolo, y cada uno existe por un fallo concreto
que se pudo reproducir:

- **El arriendo tiene testigo.** Cerrar un trabajo exige presentar el testigo
  vigente. Un worker que revive despues de que otro recupero el trabajo no
  escribe nada: ni resultado, ni estado, ni puntero.
- **Terminal y sin puntero son un solo hecho.** Ocurren en la misma transaccion,
  dentro de `finish_run`. La version anterior borraba el puntero desde fuera, sin
  comprobar nada, y podia dejar un trabajo en `running` sin puntero: invisible
  para siempre, en ninguna cola y en ninguna lista.
- **El worker no libera nada por su cuenta.** La recuperacion de un arriendo
  vencido la hace `claim_next_run`, que ve las dos filas a la vez.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import psycopg

from fincilia_contracts.extraction import ExtractionError, extract
from fincilia_contracts.ingestion import RejectedUpload, decide_promotion
from fincilia_contracts.profiling import UnprofilableFile, profile

logger = logging.getLogger("fincilia.worker.jobs")

# Mas que cualquier perfilado razonable, y menos que la paciencia de un operador.
# Un trabajo que dure mas que su arriendo se recupera y se ejecuta otra vez: la
# ejecucion es at-least-once y los efectos son idempotentes por restriccion.
LEASE_SECONDS = 300

# Clases de fallo del contrato declarado. `unknown` no se reintenta en silencio:
# acaba en carta muerta marcada para una persona.
RETRYABLE = "retryable"
FATAL = "fatal"
UNKNOWN = "unknown"

# Version del escaner. Forma parte de la clave de la decision: el mismo escaner
# sobre el mismo artefacto es una sola decision, y reejecutarlo no crea otra.
# Cuando el escaner cambie de verdad, esto sube y la decision se puede revisar
# sin reescribir la anterior.
SCANNER_RELEASE = "scan-1"


@dataclass(frozen=True)
class Claim:
    run_id: str
    company_id: str
    artifact_id: str
    kind: str
    attempt: int
    lease_token: str


def claim_next(connection: psycopg.Connection, worker: str,
               lease_seconds: int = LEASE_SECONDS) -> Claim | None:
    """Reclama el siguiente trabajo disponible, o `None` si no hay.

    Se llama **sin** contexto de empresa: la funcion lo descubre del puntero, que
    es lo unico legible sin contexto y solo lleva identificadores.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT run_id::text, company_id::text, artifact_id::text, kind, "
            "       attempt, lease_token::text "
            "FROM fincilia.claim_next_run(%s, %s)", (worker, lease_seconds))
        row = cursor.fetchone()
    return Claim(*row) if row else None


def finish(connection: psycopg.Connection, claim: Claim, *,
           result: dict | None = None, error_code: str | None = None,
           failure_class: str | None = None) -> str:
    """Cierra un trabajo. Devuelve el desenlace que decidio la base.

    `stale_lease` significa que este worker ya no es el dueno: otro recupero el
    trabajo mientras tanto. No es un error a reintentar; es una orden de soltar.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT fincilia.finish_run(%s, %s, %s::jsonb, %s, %s)",
            (claim.run_id, claim.lease_token,
             None if result is None else dumps(result), error_code, failure_class))
        row = cursor.fetchone()
    return row[0] if row else "unknown"


def dumps(payload) -> str:
    import json
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def run_profile(payload: bytes) -> tuple[dict | None, str | None, str | None]:
    """Perfila unos bytes. Devuelve `(resultado, codigo, clase_de_fallo)`.

    El resultado no lleva ni un valor del fichero: solo su forma. Un perfil que
    transcribiera datos seria una copia parcial del documento viviendo donde vive
    el metadato, con otras reglas de acceso.
    """
    try:
        table = profile(payload)
    except UnprofilableFile as error:
        # El fichero es el que es: reintentarlo dara lo mismo.
        logger.warning("unprofilable artifact: %s", error)
        return None, "unprofilable", FATAL
    except Exception:  # noqa: BLE001 - un fallo raro no tumba el worker
        # `unknown_failure_action: fail_closed_requires_triage`. Lo que no se supo
        # clasificar no se reintenta a ciegas: acaba delante de una persona.
        logger.exception("unexpected profiling failure")
        return None, "profiling_error", UNKNOWN
    return table.as_dict(), None, None


def run_extract(payload: bytes):
    """Lee un fichero entero. Devuelve `(extraccion, codigo, clase_de_fallo)`.

    A diferencia del perfilado, esto **si** devuelve valores, y por eso lo que
    sale no va al resultado de la ejecucion: va a `raw_record`, que exige
    contexto de empresa. El resultado solo lleva la forma.
    """
    try:
        return extract(payload), None, None
    except ExtractionError as error:
        # El fichero es el que es: releerlo dara lo mismo.
        logger.warning("unextractable artifact: %s", error)
        return None, "unextractable", FATAL
    except Exception:  # noqa: BLE001 - un fallo raro no tumba el worker
        logger.exception("unexpected extraction failure")
        return None, "extraction_error", UNKNOWN


def run_scan(payload: bytes, filename: str) -> tuple[dict | None, str | None, str | None]:
    """Decide si unos bytes pueden salir de cuarentena.

    Devuelve `(decision, codigo, clase_de_fallo)`. Un formato que no se sabe
    inspeccionar **no es un fallo**: es una decision de no promover, con su motivo
    escrito, y el trabajo termina bien.
    """
    try:
        decision = decide_promotion(payload, filename)
    except RejectedUpload as error:
        # Lo que ni siquiera se puede examinar se queda donde esta. Reintentarlo
        # daria lo mismo.
        logger.warning("unscannable artifact: %s", error)
        return None, "unscannable", FATAL
    except Exception:  # noqa: BLE001
        logger.exception("unexpected scan failure")
        return None, "scan_error", UNKNOWN
    return decision.as_dict(), None, None

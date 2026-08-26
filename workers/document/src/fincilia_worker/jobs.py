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

from fincilia_contracts.extraction import ExtractionError
from fincilia_contracts.ingestion import RejectedUpload, decide_promotion
from fincilia_platform.objects import ObjectStoreError
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
    issued_context_id: str | None


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
        if row is None:
            return None
        # La empresa proviene de la funcion definer, no del mensaje ni del
        # cliente. Se fija solo para leer la fila RLS que acaba de reclamarse.
        cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                       (str(row[1]),))
        cursor.execute(
            "SELECT issued_context_id::text FROM fincilia.processing_run "
            "WHERE run_id = %s", (str(row[0]),))
        context_row = cursor.fetchone()
    return Claim(*row, context_row[0] if context_row else None)


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


class RawRecordConflict(RuntimeError):
    """Un tramo ya escrito no coincide con lo que esta lectura produce.

    No es un choque de unicidad cualquiera: la fila que ya esta y la que llega
    dicen cosas distintas sobre el **mismo** registro del mismo fichero.
    Reintentar no lo arregla —volveria a divergir— y quedarse con una de las dos
    en silencio deja publicada una evidencia que nadie eligio.
    """


class StaleLease(RuntimeError):
    """El worker ya no puede demostrar que posee el trabajo.

    No se clasifica como fallo del documento ni se intenta cerrar el run: el
    propietario vigente o el recuperador son los unicos que pueden decidirlo.
    """


def classify_extraction(error: Exception) -> tuple[str, str]:
    """Que hacer con un fallo al extraer: `(codigo, clase_de_fallo)`.

    Es lo unico de la extraccion que sigue siendo una decision y no una lectura,
    y por eso vive aqui separado: de esta clasificacion depende si un trabajo se
    reintenta, muere, o acaba delante de una persona.

    **No lee el fichero.** La lectura es una corriente que el worker consume por
    tandas; sostenerla entera para poder clasificar un fallo seria volver a
    tener el fichero en memoria por si acaso.
    """
    if isinstance(error, RawRecordConflict):
        # Fatal a proposito: el reintento leeria lo mismo y volveria a chocar.
        # Lo que hace falta es que alguien mire por que dos lecturas del mismo
        # tramo no coinciden.
        return "raw_record_conflict", FATAL
    if isinstance(error, ExtractionError):
        # El fichero es el que es: releerlo dara lo mismo.
        logger.warning("unextractable artifact: %s", error)
        return "unextractable", FATAL
    if isinstance(error, ObjectStoreError):
        # La fila dice que el objeto esta y el objeto no esta. Puede ser el
        # almacen, no la evidencia.
        logger.error("evidence unreadable: %s", error)
        return "evidence_unreadable", RETRYABLE
    # `unknown_failure_action: fail_closed_requires_triage`. Lo que no se supo
    # clasificar no se reintenta a ciegas.
    logger.exception("unexpected extraction failure", exc_info=error)
    return "extraction_error", UNKNOWN


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

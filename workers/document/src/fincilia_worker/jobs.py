"""Toma de trabajos y perfilado de documentos.

El worker no decide nada financiero. Lee un fichero que **ya** salio de
cuarentena, calcula su forma y la guarda. Si el fichero no se deja leer, el
trabajo queda `failed` con un codigo: fallar diciendo por que es parte del
trabajo, no una cortesia.

Reclamar es lo unico delicado. Se hace en dos pasos, y en este orden:

1. `dispatch_pointer` dice **que empresa** tiene trabajo pendiente. Es lo minimo
   que un planificador entre empresas necesita antes de poder fijar su contexto,
   y por eso esa tabla no lleva nada mas que identificadores.
2. Con el contexto ya fijado, `processing_run` -- que si tiene RLS -- decide de
   verdad si el trabajo se ejecuta, con `FOR UPDATE SKIP LOCKED`. Dos workers
   compitiendo por la misma fila no la ejecutan dos veces: el segundo la salta.

Si el proceso muere entre los dos pasos, el puntero queda reclamado y la fila en
`queued`. `release_stale` lo devuelve al reparto pasado un plazo; perder un
trabajo en silencio seria peor que ejecutarlo dos veces, y ejecutarlo dos veces
tampoco pasa porque el perfilado es idempotente sobre el mismo artefacto.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import psycopg

from fincilia_contracts.profiling import UnprofilableFile, profile

logger = logging.getLogger("fincilia.worker.jobs")

STALE_CLAIM_SECONDS = 300
MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class Claim:
    run_id: str
    company_id: str
    artifact_id: str
    kind: str
    zone: str
    object_key: str
    media_type: str


def release_stale(connection: psycopg.Connection, *,
                  seconds: int = STALE_CLAIM_SECONDS) -> int:
    """Devuelve al reparto los punteros reclamados por un proceso que murio."""
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE fincilia.dispatch_pointer SET claimed_at = NULL, claimed_by = NULL "
            "WHERE claimed_at IS NOT NULL "
            "  AND claimed_at < now() - make_interval(secs => %s) "
            "  AND run_id IN (SELECT run_id FROM fincilia.dispatch_pointer)",
            (seconds,))
        return cursor.rowcount


def take_pointer(connection: psycopg.Connection, worker: str) -> tuple[str, str] | None:
    """Reserva un puntero pendiente. Devuelve `(run_id, company_id)`."""
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE fincilia.dispatch_pointer SET claimed_at = now(), claimed_by = %s "
            "WHERE run_id = ("
            "  SELECT run_id FROM fincilia.dispatch_pointer WHERE claimed_at IS NULL "
            "  ORDER BY queued_at FOR UPDATE SKIP LOCKED LIMIT 1) "
            "RETURNING run_id::text, company_id::text", (worker,))
        row = cursor.fetchone()
    return (row[0], row[1]) if row else None


def start_run(connection: psycopg.Connection, run_id: str) -> Claim | None:
    """Marca el trabajo como en curso dentro del contexto de su empresa.

    Devuelve `None` si otro lo tomo antes o si el artefacto no esta en `raw`: un
    fichero en cuarentena no se procesa, aunque alguien haya encolado su trabajo.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT r.run_id::text, r.company_id::text, r.artifact_id::text, r.kind, "
            "       a.zone, a.object_key, a.media_type "
            "FROM fincilia.processing_run r "
            "JOIN fincilia.source_artifact a ON a.artifact_id = r.artifact_id "
            "WHERE r.run_id = %s AND r.status = 'queued' "
            "FOR UPDATE OF r SKIP LOCKED", (run_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        claim = Claim(*row)
        if claim.zone != "raw":
            cursor.execute(
                "UPDATE fincilia.processing_run SET status = 'failed', "
                "started_at = now(), finished_at = now(), error_code = %s "
                "WHERE run_id = %s", ("artifact_not_promoted", run_id))
            return None
        cursor.execute(
            "UPDATE fincilia.processing_run SET status = 'running', started_at = now() "
            "WHERE run_id = %s", (run_id,))
    return claim


def finish_run(connection: psycopg.Connection, run_id: str, *,
               result: dict | None = None, error_code: str | None = None) -> None:
    status = "failed" if error_code else "succeeded"
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE fincilia.processing_run SET status = %s, finished_at = now(), "
            "result = COALESCE(%s::jsonb, result), error_code = %s WHERE run_id = %s",
            (status, None if result is None else _dumps(result), error_code, run_id))


def drop_pointer(connection: psycopg.Connection, run_id: str) -> None:
    """El puntero desaparece al terminar. La fila de verdad se queda."""
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM fincilia.dispatch_pointer WHERE run_id = %s",
                       (run_id,))


def _dumps(payload: dict) -> str:
    import json
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def run_profile(payload: bytes) -> tuple[dict | None, str | None]:
    """Perfila unos bytes. Devuelve `(resultado, codigo_de_error)`.

    El resultado no lleva ni un valor del fichero: solo su forma. Un perfil que
    transcribiera datos seria una copia parcial del documento viviendo donde vive
    el metadato, con otras reglas de acceso.
    """
    try:
        table = profile(payload)
    except UnprofilableFile as error:
        logger.warning("unprofilable artifact: %s", error)
        return None, "unprofilable"
    except Exception as error:  # noqa: BLE001 - un fallo raro no tumba el worker
        logger.exception("unexpected profiling failure")
        return None, f"profiling_{type(error).__name__.lower()}"[:80]
    return table.as_dict(), None

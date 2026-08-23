"""Bucle principal del worker de documentos.

Toma trabajos de la cola, lee el fichero de la zona de evidencia, calcula su
forma y guarda el perfil. Nada de esto decide nada financiero: el worker no
publica movimientos, no concilia y no cierra nada.

Antes de trabajar comprueba que alcanza sus dependencias. Es deliberado que
**no** sea un mock que devuelve constantes: si PostgreSQL, el esquema, Valkey o
el almacen de objetos no responden, el worker no se declara sano.

El latido es un fichero en `/tmp` con `mtime` fresco. Se eligio asi porque el
worker no expone HTTP: darle un puerto solo para el healthcheck seria superficie
sin uso, y un fichero con marca de tiempo distingue "vivo" de "colgado", que es
justo lo que un proceso de fondo necesita comunicar.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import time
from pathlib import Path
from types import FrameType

# El worker comparte la configuracion tipada de la API: mismas variables, mismas
# reglas fail-closed. Duplicarlas seria pedir que se separen con el tiempo.
sys.path.insert(0, "/app/src")

from fincilia_contracts.release import digest_of  # noqa: E402
from fincilia_platform.db import Database  # noqa: E402
from fincilia_platform.objects import ObjectStoreError, S3ObjectStore  # noqa: E402
from fincilia_worker import jobs  # noqa: E402
from fincilia_worker.config import WorkerSettings, load_settings  # noqa: E402
from fincilia_worker.probes import probe_all  # noqa: E402

HEARTBEAT_PATH = Path("/tmp/fincilia-worker-alive")
HEARTBEAT_INTERVAL_SECONDS = 5
STARTUP_GRACE_SECONDS = 30
IDLE_SLEEP_SECONDS = 2

logger = logging.getLogger("fincilia.worker")
_running = True


def _stop(signum: int, _frame: FrameType | None) -> None:
    global _running
    logger.info("received signal %s; draining", signum)
    _running = False


def wait_for_dependencies(settings: WorkerSettings, *, deadline: float) -> bool:
    """Espera a que las tres dependencias respondan, sin superar el plazo."""
    while time.monotonic() < deadline:
        results = probe_all(settings)
        if all(result.healthy for result in results):
            logger.info("dependencies ready: %s",
                        ", ".join(f"{r.name}={r.status}" for r in results))
            return True
        logger.warning("waiting on dependencies: %s",
                       ", ".join(f"{r.name}={r.status}" for r in results if not r.healthy))
        time.sleep(2)
    return False


def beat() -> None:
    """Marca de vida. Un fichero con `mtime` fresco distingue vivo de colgado."""
    HEARTBEAT_PATH.write_text(str(int(time.time())), encoding="utf-8")


def main() -> int:
    settings = load_settings()
    logging.basicConfig(level=settings.log_level.upper(),
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    logger.info("starting %s in %s", settings.service_name, settings.env)
    if not wait_for_dependencies(settings,
                                 deadline=time.monotonic() + STARTUP_GRACE_SECONDS):
        logger.error("dependencies did not become ready; refusing to report healthy")
        return 1

    database = Database(settings)
    store = S3ObjectStore(settings)
    identity = f"{settings.service_name}-{os.getpid()}"

    last_beat = 0.0
    try:
        while _running:
            now = time.monotonic()
            if now - last_beat >= HEARTBEAT_INTERVAL_SECONDS:
                beat()
                last_beat = now
            if not process_one(database, store, identity):
                # Sin trabajo no se martillea la base: se espera un poco. Sondear
                # en bucle cerrado consume mas que el trabajo que busca.
                time.sleep(IDLE_SLEEP_SECONDS)
    finally:
        database.close()

    logger.info("stopped cleanly")
    return 0


def process_one(database: Database, store, identity: str) -> bool:
    """Toma un trabajo, lo hace y lo cierra. Devuelve si habia algo que hacer.

    Tres transacciones cortas, no una larga: mantener abierta la del reclamo
    mientras se descarga un fichero dejaria una fila bloqueada durante toda la
    descarga. Lo que sostiene la correccion entre ellas no es el bloqueo, es el
    testigo de arriendo.
    """
    try:
        # Sin contexto de empresa: la funcion lo descubre del puntero.
        with database.session() as connection:
            claim = jobs.claim_next(connection, identity)
    except Exception:  # noqa: BLE001 - la base puede estar reiniciandose
        logger.exception("could not reach the dispatch queue")
        return False
    if claim is None:
        return False

    result: dict | None = None
    error_code: str | None = None
    failure_class: str | None = None
    # Un escaneo lee de cuarentena; perfilar y extraer, de la zona de evidencia.
    # **Nada se extrae desde cuarentena**: si se pudiera, la regla de inspeccion
    # previa no serviria de nada, y la vista previa mostraria valores de un
    # fichero que nadie ha mirado.
    zone = "quarantine" if claim.kind == "scan" else "raw"
    try:
        artifact = _artifact_row(database, claim)
        payload = store.get(zone, artifact["object_key"])
    except ObjectStoreError as error:
        # La fila dice que el objeto esta y el objeto no esta. Es reintentable:
        # puede ser el almacen, no la evidencia.
        logger.error("evidence unreadable for run %s: %s", claim.run_id, error)
        error_code, failure_class = "evidence_unreadable", jobs.RETRYABLE
    except Exception:  # noqa: BLE001
        logger.exception("unexpected failure reading evidence for run %s", claim.run_id)
        error_code, failure_class = "evidence_error", jobs.UNKNOWN
    else:
        if claim.kind == "scan":
            result, error_code, failure_class = jobs.run_scan(
                payload, artifact["filename"])
            if result is not None:
                try:
                    _record_decision(database, store, claim, artifact, payload, result)
                except Exception:  # noqa: BLE001
                    logger.exception("could not record the promotion decision")
                    result, error_code, failure_class = None, "decision_unstorable", \
                        jobs.RETRYABLE
        elif claim.kind == "extract":
            extraction, error_code, failure_class = jobs.run_extract(payload)
            if extraction is not None:
                try:
                    _store_records(database, claim, artifact, extraction)
                except Exception:  # noqa: BLE001
                    logger.exception("could not store the extracted records")
                    error_code, failure_class = "records_unstorable", jobs.RETRYABLE
                else:
                    # El resultado de la ejecucion lo lee cualquiera que vea el
                    # documento: lleva la forma, y los valores se quedan en
                    # `raw_record`, que exige contexto de empresa.
                    result = extraction.as_dict()
        else:
            result, error_code, failure_class = jobs.run_profile(payload)

    try:
        with database.session(company_id=claim.company_id) as connection:
            outcome = jobs.finish(connection, claim, result=result,
                                  error_code=error_code, failure_class=failure_class)
    except Exception:  # noqa: BLE001
        # No se puede cerrar el trabajo. **No se toca nada mas**: el arriendo
        # vencera y otro worker lo recuperara. Inventar aqui una limpieza es lo
        # que antes dejaba trabajos invisibles para siempre.
        logger.exception("could not close run %s; leaving it to the lease",
                         claim.run_id)
        return True

    if outcome == "stale_lease":
        # Otro worker recupero este trabajo mientras tanto. No es un error a
        # reintentar: es una orden de soltar sin escribir nada.
        logger.warning("run %s was recovered by another worker; dropping it",
                       claim.run_id)
    else:
        logger.info("run %s finished: %s", claim.run_id, outcome)
    return True


def _artifact_row(database: Database, claim: "jobs.Claim") -> dict:
    """Datos del artefacto, leidos dentro del alcance de su empresa."""
    with database.session(company_id=claim.company_id) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT object_key, filename, content_sha256 "
                "FROM fincilia.source_artifact WHERE artifact_id = %s",
                (claim.artifact_id,))
            row = cursor.fetchone()
    if row is None:
        raise ObjectStoreError("the artifact is not visible in its own context")
    return {"object_key": row[0], "filename": row[1], "content_sha256": row[2]}


def _record_decision(database: Database, store, claim: "jobs.Claim", artifact: dict,
                     payload: bytes, decision: dict) -> None:
    """Escribe la decision y, si promueve, copia la evidencia a su zona.

    El orden importa y no es arbitrario: primero el objeto en `raw`, despues la
    fila que dice que esta ahi. Al reves, una caida entre medias dejaria una
    decision afirmando que la evidencia esta promovida cuando no lo esta, y esa
    fila la creeria todo lo que viniera despues.

    La clave del objeto sale del contenido, asi que copiarlo dos veces escribe lo
    mismo en el mismo sitio: reintentar un escaneo es inocuo.
    """
    raw_key = None
    if decision["decision"] == "promoted":
        store.put("raw", artifact["object_key"], payload,
                  content_type=decision["media_type"],
                  metadata={"company": claim.company_id,
                            "sha256": artifact["content_sha256"]})
        raw_key = artifact["object_key"]

    with database.session(company_id=claim.company_id) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO fincilia.promotion_decision (decision_id, company_id, "
                "artifact_id, run_id, decision, reason_code, scanner_release, "
                "media_type, internal_type, findings, raw_object_key) "
                "VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s) "
                "ON CONFLICT (artifact_id, scanner_release) DO NOTHING",
                (claim.company_id, claim.artifact_id, claim.run_id,
                 decision["decision"], decision["reason_code"], jobs.SCANNER_RELEASE,
                 decision["media_type"], decision.get("internal_type", ""),
                 jobs.dumps(decision.get("findings", [])), raw_key))
            # Solo lo promovido se lee. Encolar una lectura sobre algo que sigue
            # en cuarentena seria pasear por otro proceso justo lo que no ha
            # pasado inspeccion.
            #
            # Son dos trabajos independientes y no uno con dos partes: perfilar
            # mide sin transcribir y extraer transcribe con coordenadas. Que uno
            # falle no debe impedir el otro.
            if decision["decision"] == "promoted":
                for kind in ("profile", "extract"):
                    cursor.execute(
                        "SELECT fincilia.enqueue_processing_run(%s, %s, %s)",
                        (claim.company_id, claim.artifact_id, kind))
            cursor.execute(
                "INSERT INTO fincilia.audit_event (audit_event_id, company_id, "
                "subject_id, action, resource_kind, resource_ref, outcome, detail) "
                "VALUES (gen_random_uuid(), %s, NULL, 'document.promotion', 'document', "
                "%s, %s, %s::jsonb)",
                (claim.company_id, claim.artifact_id,
                 "allowed" if decision["decision"] == "promoted" else "denied",
                 jobs.dumps({"decision": decision["decision"],
                             "reason": decision["reason_code"],
                             "scanner": jobs.SCANNER_RELEASE})))


# Filas por sentencia al guardar lo extraido. Igual que en la publicacion: lo
# bastante grande para amortizar el viaje, lo bastante pequeno para no sostener
# una copia entera del fichero en memoria.
STORE_BATCH = 1_000


def _batched(items, size: int):
    """Recorre en tandas sin copiar la secuencia entera."""
    for start in range(0, len(items), size):
        yield items[start:start + size]


def _store_records(database: Database, claim: "jobs.Claim", artifact: dict,
                   extraction) -> None:
    """Guarda cada registro leido con su coordenada exacta.

    `ON CONFLICT DO NOTHING` sobre `(processing_run_id, record_ordinal)` hace
    inocuo el reintento: un arriendo vencido y recuperado vuelve a ejecutar esta
    misma extraccion, y la segunda vez no duplica nada.

    Se escriben **todos** los registros, membrete y cabecera incluidos. Decidir
    cuales son datos es del mapeo; guardar solo los que hoy parecen datos
    obligaria a releer la evidencia en cuanto alguien moviera la cabecera.
    """
    sha256 = artifact["content_sha256"]
    total = 0
    with database.session(company_id=claim.company_id) as connection:
        with connection.cursor() as cursor:
            # Por tandas y sin construir la lista entera: serializar cien mil
            # filas de golpe deja en memoria una segunda copia completa del
            # fichero, al lado de la que ya tiene la extraccion.
            for batch in _batched(extraction.rows, STORE_BATCH):
                cursor.executemany(
                    "INSERT INTO fincilia.raw_record (raw_record_id, company_id, "
                    "artifact_id, processing_run_id, record_ordinal, origin_locator, "
                    "raw_values, values_digest) VALUES (gen_random_uuid(), %s, %s, %s, "
                    "%s, %s::jsonb, %s::jsonb, %s) "
                    "ON CONFLICT (processing_run_id, record_ordinal) DO NOTHING",
                    [(claim.company_id, claim.artifact_id, claim.run_id,
                      row.record_ordinal, jobs.dumps(row.locator(sha256)),
                      jobs.dumps(list(row.values)), digest_of(list(row.values)))
                     for row in batch])
                total += len(batch)
            # La auditoria dice cuantos registros se leyeron y de donde. **Ni un
            # valor**: el evento lo lee quien tiene `audit.read`, que no es
            # necesariamente quien puede ver el contenido del documento.
            cursor.execute(
                "INSERT INTO fincilia.audit_event (audit_event_id, company_id, "
                "subject_id, action, resource_kind, resource_ref, outcome, detail) "
                "VALUES (gen_random_uuid(), %s, NULL, 'document.extraction', "
                "'document', %s, 'allowed', %s::jsonb)",
                (claim.company_id, claim.artifact_id,
                 jobs.dumps({"records": total,
                             "truncated": extraction.truncated,
                             "truncation_reason": extraction.truncation_reason,
                             "run": claim.run_id})))


if __name__ == "__main__":
    raise SystemExit(main())

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
from fincilia_platform.gates import verify_configured_gate  # noqa: E402
from fincilia_platform.objects import ObjectStoreError, S3ObjectStore  # noqa: E402
from fincilia_platform.observability import (  # noqa: E402
    configure as configure_observability,
    correlation,
    log_event,
)
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
    if settings.real_data_enabled:
        verify_configured_gate(settings, required_gate="DRG-01")
    configure_observability(settings.service_name, settings.log_level)
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    log_event(logger, logging.INFO, "worker.starting",
              environment=settings.env, release_id=settings.release_id,
              revision=settings.build_revision)
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

    log_event(logger, logging.INFO, "worker.stopped", outcome="clean")
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

    with correlation(claim.run_id):
        return _process_claim(database, store, claim)


def _process_claim(database: Database, store, claim: "jobs.Claim") -> bool:
    """Procesa un claim bajo su correlation ID y lo libera al terminar."""

    result: dict | None = None
    error_code: str | None = None
    failure_class: str | None = None
    # Un escaneo lee de cuarentena; perfilar y extraer, de la zona de evidencia.
    # **Nada se extrae desde cuarentena**: si se pudiera, la regla de inspeccion
    # previa no serviria de nada, y la vista previa mostraria valores de un
    # fichero que nadie ha mirado.
    zone = "quarantine" if claim.kind == "scan" else "raw"

    # Extraer **no** descarga el fichero: lo lee en corriente y lo escribe por
    # tandas. Cien mil filas costaban doscientos megabytes de bytes mas la lista
    # entera de registros al lado, y ninguna de las dos cosas hace falta para
    # escribir la fila que se acaba de leer.
    if claim.kind == "extract":
        return _extract_streaming(database, store, claim)

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
        else:
            result, error_code, failure_class = jobs.run_profile(
                payload, internal_type=artifact["internal_type"],
                sheet_identity=artifact.get("sheet_identity"))

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
                "SELECT fincilia.hold_processing_lease(%s, %s)",
                (claim.run_id, claim.lease_token))
            if cursor.fetchone()[0] is not True:
                raise jobs.StaleLease(
                    "the processing lease or authorization context is no longer valid")
            cursor.execute(
                "SELECT a.object_key, a.filename, a.content_sha256, "
                "       COALESCE((SELECT p.internal_type "
                "         FROM fincilia.promotion_decision p "
                "        WHERE p.artifact_id = a.artifact_id "
                "          AND p.company_id = a.company_id "
                "          AND p.decision = 'promoted' "
                "        ORDER BY p.decided_at DESC, p.decision_id DESC LIMIT 1), ''), "
                "       selection.sheet_identity "
                "FROM fincilia.source_artifact a "
                "LEFT JOIN fincilia.spreadsheet_selection selection "
                "  ON selection.artifact_id = a.artifact_id "
                " AND selection.company_id = a.company_id "
                "WHERE a.artifact_id = %s",
                (claim.artifact_id,))
            row = cursor.fetchone()
    if row is None:
        raise ObjectStoreError("the artifact is not visible in its own context")
    return {"object_key": row[0], "filename": row[1], "content_sha256": row[2],
            "internal_type": row[3], "sheet_identity": row[4]}


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
            if (decision["decision"] == "promoted"
                    and not decision.get("requires_selection", False)):
                for kind in ("profile", "extract"):
                    if claim.issued_context_id is None:
                        # Compatibilidad expand-only para un scan creado antes
                        # de V0022. Los productores nuevos nunca pasan por aqui.
                        cursor.execute(
                            "SELECT fincilia.enqueue_processing_run(%s, %s, %s)",
                            (claim.company_id, claim.artifact_id, kind))
                    else:
                        cursor.execute(
                            "SELECT fincilia.enqueue_processing_run(%s, %s, %s, %s)",
                            (claim.company_id, claim.artifact_id, kind,
                             claim.issued_context_id))
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


# Filas por sentencia al guardar lo extraido. Lo bastante grande para amortizar
# el viaje, lo bastante pequeno para que la tanda en curso sea lo unico vivo.
STORE_BATCH = 1_000


def _extract_streaming(database: Database, store, claim: "jobs.Claim") -> bool:
    """Lee el fichero en corriente y escribe cada tanda segun llega.

    Tres transacciones cortas por tanda y ninguna larga: mantener abierta una
    mientras se descarga dejaria una fila bloqueada durante toda la lectura, y
    sostener el fichero para poder reintentar es exactamente lo que hacia que
    cien mil filas costaran doscientos megabytes.

    La reanudacion es idempotente por construccion: `uq_raw_record_ordinal` sobre
    `(processing_run_id, record_ordinal)` con `ON CONFLICT DO NOTHING` hace que
    volver a escribir una tanda no duplique nada, y un reintento conserva el
    mismo `run_id`.
    """
    from fincilia_contracts.extraction import (
        StreamOutcome, extraction_summary, sniff, stream_records)

    error_code: str | None = None
    failure_class: str | None = None
    result: dict | None = None
    settled: str | None = None
    stale_lease = False

    try:
        artifact = _artifact_row(database, claim)
    except ObjectStoreError as error:
        logger.error("evidence unreadable for run %s: %s", claim.run_id, error)
        error_code, failure_class = "evidence_unreadable", jobs.RETRYABLE
    else:
        outcome = StreamOutcome()
        stream = None
        try:
            if artifact["internal_type"] in {"xlsx", "ods"}:
                if artifact["internal_type"] == "ods":
                    from fincilia_contracts.open_document import (
                        OpenDocumentOutcome,
                        open_document_summary,
                        sniff_open_document,
                        stream_open_document_rows,
                    )

                    payload = store.get("raw", artifact["object_key"])
                    _, preamble = sniff_open_document(
                        payload, sheet_identity=artifact.get("sheet_identity"))
                    ods_outcome = OpenDocumentOutcome()
                    written = _store_stream(
                        database, claim, artifact,
                        stream_open_document_rows(
                            payload, preamble, outcome=ods_outcome,
                            artifact_sha256=artifact["content_sha256"]))
                    result = open_document_summary(preamble, ods_outcome)
                else:
                    from fincilia_contracts.spreadsheet import (
                        SpreadsheetOutcome,
                        sniff_workbook,
                        spreadsheet_summary,
                        stream_workbook_rows,
                    )

                    payload = store.get("raw", artifact["object_key"])
                    _, preamble = sniff_workbook(
                        payload, sheet_identity=artifact.get("sheet_identity"))
                    xlsx_outcome = SpreadsheetOutcome()
                    written = _store_stream(
                        database, claim, artifact,
                        stream_workbook_rows(
                            payload, preamble, outcome=xlsx_outcome,
                            artifact_sha256=artifact["content_sha256"]))
                    result = spreadsheet_summary(preamble, xlsx_outcome)
            else:
                stream = store.open("raw", artifact["object_key"])
                preamble, reader = sniff(stream)
                written = _store_stream(
                    database, claim, artifact,
                    stream_records(reader, preamble, outcome=outcome,
                                   artifact_sha256=artifact["content_sha256"]))
                result = extraction_summary(preamble, outcome)
            # Dos cifras distintas y las dos ciertas: cuantas filas escribio
            # **este** intento, y cuantas hay. Al reanudar se separan, y es
            # justo entonces cuando una sola no basta para saber que paso.
            #
            # El recuento y la auditoria pertenecen al mismo limite de fallo que
            # la extraccion. Si cualquiera falla, el run no puede declararse
            # exitoso con evidencia sin contar o sin rastro.
            result["inserted_records"] = written
            settled = _settle_extraction(database, claim, result)
        except jobs.StaleLease:
            # No es un fallo de la evidencia. Este proceso dejo de ser el dueno
            # y no puede escribir ni decidir el desenlace del trabajo.
            stale_lease = True
            result = None
        except Exception as error:  # noqa: BLE001 - un fallo raro no tumba el worker
            # La clasificacion vive en `jobs` porque de ella depende si el
            # trabajo se reintenta, muere o acaba delante de una persona, y eso
            # se prueba sin base de datos.
            error_code, failure_class = jobs.classify_extraction(error)
            result = None
        finally:
            # Cerrar pase lo que pase: una corriente abierta retiene una conexion
            # del pool de HTTP del almacen hasta que alguien la suelta.
            closer = getattr(stream, "close", None)
            if closer is not None:
                try:
                    closer()
                except Exception:  # noqa: BLE001 - cerrar no puede tumbar nada
                    logger.debug("the evidence stream was already closed")

    if stale_lease:
        logger.warning("run %s lost its lease while storing; dropping it",
                       claim.run_id)
        return True

    # El camino exitoso ya cerro run y auditoria en una sola transaccion. No se
    # invoca `finish_run` dos veces: el segundo resultado seria `stale_lease` y
    # esconderia el desenlace real que acabamos de obtener.
    if settled is not None:
        if settled == "stale_lease":
            logger.warning("run %s was recovered by another worker; dropping it",
                           claim.run_id)
        else:
            logger.info("run %s finished: %s", claim.run_id, settled)
        return True

    try:
        with database.session(company_id=claim.company_id) as connection:
            settled = jobs.finish(connection, claim, result=result,
                                  error_code=error_code, failure_class=failure_class)
    except Exception:  # noqa: BLE001
        logger.exception("could not close run %s; leaving it to the lease",
                         claim.run_id)
        return True
    if settled == "stale_lease":
        logger.warning("run %s was recovered by another worker; dropping it",
                       claim.run_id)
    else:
        logger.info("run %s finished: %s", claim.run_id, settled)
    return True


def _store_stream(database: Database, claim: "jobs.Claim", artifact: dict,
                  records) -> int:
    """Escribe los registros por tandas. Nunca sostiene mas de una.

    El generador se consume aqui y no se materializa: lo unico que vive a la vez
    es la tanda en curso, y `STORE_BATCH` la acota.
    """
    sha256 = artifact["content_sha256"]
    written = 0
    batch: list[tuple] = []
    for row in records:
        batch.append((claim.company_id, claim.artifact_id, claim.run_id,
                      row.record_ordinal, jobs.dumps(row.locator(sha256)),
                      jobs.dumps(list(row.values)), digest_of(list(row.values))))
        if len(batch) >= STORE_BATCH:
            written += _flush(database, claim, batch)
            batch = []
    if batch:
        written += _flush(database, claim, batch)
    return written


# Las columnas que escribe la extraccion, en el orden en que las arma
# `_store_stream`. `raw_record_id` y `created_at` los pone la base.
STAGED_COLUMNS = ("company_id", "artifact_id", "processing_run_id",
                  "record_ordinal", "origin_locator", "raw_values",
                  "values_digest")


# Lo que hace distinto un conflicto de otro. `IS DISTINCT FROM` y no `<>`
# porque cualquiera de los dos lados puede ser nulo, y con `<>` un nulo dejaria
# la comparacion sin ser ni cierta ni falsa: pasaria por buena.
DIVERGENT_ROWS = (
    "SELECT s.record_ordinal FROM staging_raw_record s "
    "JOIN fincilia.raw_record r "
    "  ON r.processing_run_id = s.processing_run_id "
    " AND r.record_ordinal = s.record_ordinal "
    "WHERE r.processing_run_id = %s "
    "  AND r.record_ordinal = ANY(%s::integer[]) "
    "  AND (r.company_id      IS DISTINCT FROM s.company_id "
    "   OR r.artifact_id      IS DISTINCT FROM s.artifact_id "
    "   OR r.origin_locator   IS DISTINCT FROM s.origin_locator "
    "   OR r.raw_values       IS DISTINCT FROM s.raw_values "
    "   OR r.values_digest    IS DISTINCT FROM s.values_digest) "
    "ORDER BY s.record_ordinal LIMIT 5")


def _flush(database: Database, claim: "jobs.Claim", batch: list[tuple]) -> int:
    """Una tanda, una transaccion. Devuelve lo que PostgreSQL escribio.

    La tanda entra por `COPY` a una tabla `TEMPORARY ... ON COMMIT DROP` y de ahi
    a `raw_record` con un `INSERT ... SELECT`. `COPY` directo sobre la tabla con
    RLS no es una opcion —PostgreSQL lo rechaza— y el rodeo por la temporal no
    debilita nada: la politica sigue activa y forzada sobre el destino, que es
    donde tiene que estar la frontera. La temporal no lleva politica porque no la
    necesita: es de esta sesion y desaparece al confirmar.

    `db/spikes/staging_benchmark.py` es lo que autoriza esta ruta: comprueba las
    diez propiedades contra PostgreSQL real y mide. En la corrida que la adopto
    salio en 1,9x sobre el `INSERT` multifila con tandas de quinientas.

    Reintentar no duplica —lo impide la unicidad— pero **no todos los conflictos
    son reanudaciones**. Uno identico lo es y se ignora. Uno que trae otro
    localizador, otros valores u otra huella es otra lectura del mismo tramo, y
    entonces la tanda entera se deshace: entre dos evidencias que se contradicen,
    quedarse con la que llego primero es elegir sin mirar.
    """
    with database.session(company_id=claim.company_id) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT fincilia.hold_processing_lease(%s, %s)",
                (claim.run_id, claim.lease_token))
            held = cursor.fetchone()
            if not held or held[0] is not True:
                raise jobs.StaleLease(
                    "the processing lease is expired, replaced or outside the "
                    "current company context")
            cursor.execute(
                "CREATE TEMPORARY TABLE staging_raw_record ("
                "  company_id uuid, artifact_id uuid, processing_run_id uuid,"
                "  record_ordinal integer, origin_locator jsonb, raw_values jsonb,"
                "  values_digest char(64)) ON COMMIT DROP")
            with cursor.copy("COPY staging_raw_record (" +
                             ", ".join(STAGED_COLUMNS) + ") FROM STDIN") as copy:
                for row in batch:
                    copy.write_row(row)
            cursor.execute(
                "INSERT INTO fincilia.raw_record (raw_record_id, company_id, "
                "artifact_id, processing_run_id, record_ordinal, origin_locator, "
                "raw_values, values_digest) "
                "SELECT gen_random_uuid(), " + ", ".join(STAGED_COLUMNS) + " "
                "FROM staging_raw_record "
                "ON CONFLICT (processing_run_id, record_ordinal) DO NOTHING")
            # `rowcount` tras un `INSERT` cuenta las filas **insertadas**: las
            # que `DO NOTHING` salto no entran. Es el unico numero de aqui que
            # puede sostener una afirmacion sobre lo que hay en la base.
            inserted = cursor.rowcount
            if inserted < 0 or inserted > len(batch):
                raise RuntimeError(
                    "PostgreSQL did not report a valid inserted row count")
            # La ruta normal no tiene conflictos. Comparar toda la temporal con
            # lo ya acumulado antes de cada INSERT hacia que el coste creciera
            # con cada tanda y convirtio 100.000 filas en un truncamiento por
            # tiempo. Solo hay algo que adjudicar cuando PostgreSQL salto al
            # menos una fila. La comprobacion sigue dentro de la transaccion:
            # si encuentra una divergencia, tambien revierte lo insertado por
            # esta tanda.
            if inserted != len(batch):
                cursor.execute(DIVERGENT_ROWS,
                               (claim.run_id, [row[3] for row in batch]))
                clash = [int(row[0]) for row in cursor.fetchall()]
                if clash:
                    raise jobs.RawRecordConflict(
                        "records " + ", ".join(str(item) for item in clash) +
                        " of this run already exist with different content; two "
                        "readings of the same file do not agree")
    return inserted


def _settle_extraction(database: Database, claim: "jobs.Claim",
                       result: dict) -> str:
    """Cuenta, cierra y audita el éxito como un único hecho durable.

    Si contar o auditar falla, la transacción revierte también `finish_run` y el
    arriendo sigue recuperable. Si el arriendo ya no pertenece a este worker,
    no deja una auditoría de éxito para un resultado que la cola rechazó.
    """
    with database.session(company_id=claim.company_id) as connection:
        result["stored_records"] = _stored_records(connection, claim)
        settled = jobs.finish(connection, claim, result=result)
        if settled == "succeeded":
            _audit_extraction(connection, claim, result)
        return settled


def _stored_records(connection, claim: "jobs.Claim") -> int:
    """Cuantas filas de esta ejecucion hay en PostgreSQL. Sin interpretar.

    Contar lo que se intento escribir da otro numero en cuanto hay una
    reanudacion, y ese numero se guarda en el resultado de la ejecucion, se
    audita y se lee para decidir. Una cifra que dice «se escribieron mil» cuando
    hay novecientas es peor que no tener cifra.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM fincilia.raw_record "
            "WHERE processing_run_id = %s", (claim.run_id,))
        return int(cursor.fetchone()[0])


def _audit_extraction(connection, claim: "jobs.Claim",
                      summary: dict) -> None:
    """Cuantos registros se leyeron y como acabo. **Ni un valor**.

    El evento lo lee quien tiene `audit.read`, que no es necesariamente quien
    puede ver el contenido del documento.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO fincilia.audit_event (audit_event_id, company_id, "
            "subject_id, action, resource_kind, resource_ref, outcome, detail) "
            "VALUES (gen_random_uuid(), %s, NULL, 'document.extraction', "
            "'document', %s, %s, %s::jsonb)",
            (claim.company_id, claim.artifact_id,
             "allowed" if summary.get("state") == "complete" else "denied",
             jobs.dumps({"records": summary.get("record_count"),
                         "stored": summary.get("stored_records"),
                         "state": summary.get("state"),
                         "reason": summary.get("truncation_reason"),
                         "object_digest": summary.get("object_digest"),
                         "record_digest": summary.get("record_digest"),
                         "run": claim.run_id})))


if __name__ == "__main__":
    raise SystemExit(main())

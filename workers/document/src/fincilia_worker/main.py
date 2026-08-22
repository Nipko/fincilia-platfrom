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
    """Toma un trabajo y lo termina. Devuelve si habia algo que hacer.

    Cada paso abre su propia transaccion con el alcance que le toca. Mantener una
    sola transaccion abierta mientras se descarga un fichero dejaria una fila
    bloqueada durante toda la descarga.
    """
    try:
        with database.session() as connection:
            jobs.release_stale(connection)
            pointer = jobs.take_pointer(connection, identity)
    except Exception:  # noqa: BLE001 - la base puede estar reiniciandose
        logger.exception("could not reach the dispatch table")
        return False
    if pointer is None:
        return False

    run_id, company_id = pointer
    try:
        with database.session(company_id=company_id) as connection:
            claim = jobs.start_run(connection, run_id)
        if claim is None:
            with database.session() as connection:
                jobs.drop_pointer(connection, run_id)
            return True

        try:
            payload = store.get(claim.zone, claim.object_key)
        except ObjectStoreError as error:
            logger.error("evidence unreadable for run %s: %s", run_id, error)
            result, error_code = None, "evidence_unreadable"
        else:
            result, error_code = jobs.run_profile(payload)

        try:
            with database.session(company_id=company_id) as connection:
                jobs.finish_run(connection, run_id, result=result,
                                error_code=error_code)
        except Exception:  # noqa: BLE001
            # Guardar el resultado puede fallar por si mismo. Dejar el trabajo en
            # `running` para siempre es peor que declararlo fallido: un trabajo
            # colgado no lo reintenta nadie y no aparece en ninguna lista.
            logger.exception("could not store the result of run %s", run_id)
            with database.session(company_id=company_id) as connection:
                jobs.finish_run(connection, run_id, error_code="result_unstorable")
        with database.session() as connection:
            jobs.drop_pointer(connection, run_id)
        logger.info("run %s finished: %s", run_id, error_code or "succeeded")
    except Exception:  # noqa: BLE001 - un trabajo roto no tumba el worker
        logger.exception("run %s failed unexpectedly", run_id)
        try:
            with database.session(company_id=company_id) as connection:
                jobs.finish_run(connection, run_id, error_code="worker_error")
        except Exception:  # noqa: BLE001 - ya se registro lo importante
            logger.exception("run %s could not be marked failed", run_id)
    return True


if __name__ == "__main__":
    raise SystemExit(main())

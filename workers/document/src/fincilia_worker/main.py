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
    try:
        payload = store.get("raw", _object_key(database, claim))
    except ObjectStoreError as error:
        # La fila dice que el objeto esta y el objeto no esta. Es reintentable:
        # puede ser el almacen, no la evidencia.
        logger.error("evidence unreadable for run %s: %s", claim.run_id, error)
        error_code, failure_class = "evidence_unreadable", jobs.RETRYABLE
    except Exception:  # noqa: BLE001
        logger.exception("unexpected failure reading evidence for run %s", claim.run_id)
        error_code, failure_class = "evidence_error", jobs.UNKNOWN
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


def _object_key(database: Database, claim: "jobs.Claim") -> str:
    """Clave del objeto del artefacto, leida dentro del alcance de su empresa."""
    with database.session(company_id=claim.company_id) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT object_key FROM fincilia.source_artifact WHERE artifact_id = %s",
                (claim.artifact_id,))
            row = cursor.fetchone()
    if row is None:
        raise ObjectStoreError("the artifact is not visible in its own context")
    return row[0]


if __name__ == "__main__":
    raise SystemExit(main())

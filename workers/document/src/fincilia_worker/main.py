"""Bucle principal del worker de documentos.

En P0 el worker todavia no procesa nada: verifica que puede alcanzar sus tres
dependencias y publica un latido. Es deliberado que **no** sea un mock que
devuelve constantes: si PostgreSQL, Valkey u object storage no responden, el
worker no se declara sano.

El latido es un fichero en `/tmp` con `mtime` fresco. Se eligio asi porque el
worker no expone HTTP: darle un puerto solo para el healthcheck seria superficie
sin uso, y un fichero con marca de tiempo distingue "vivo" de "colgado", que es
justo lo que un proceso de fondo necesita comunicar.
"""

from __future__ import annotations

import logging
import signal
import sys
import time
from pathlib import Path
from types import FrameType

# El worker comparte la configuracion tipada de la API: mismas variables, mismas
# reglas fail-closed. Duplicarlas seria pedir que se separen con el tiempo.
sys.path.insert(0, "/app/src")

from fincilia_worker.config import WorkerSettings, load_settings  # noqa: E402
from fincilia_worker.probes import probe_all  # noqa: E402

HEARTBEAT_PATH = Path("/tmp/fincilia-worker-alive")
HEARTBEAT_INTERVAL_SECONDS = 5
STARTUP_GRACE_SECONDS = 30

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

    while _running:
        beat()
        time.sleep(HEARTBEAT_INTERVAL_SECONDS)

    logger.info("stopped cleanly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

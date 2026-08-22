"""Plataforma compartida: configuracion tipada y sondas de dependencias.

Lo consumen `apps/api` y `workers/*`. Vive aqui y no en cada servicio porque dos
copias de las mismas reglas fail-closed se separan en cuanto alguien toca una.
"""

from fincilia_platform.probes import (
    CacheProbe,
    DatabaseProbe,
    ObjectStoreProbe,
    Probe,
    ProbeResult,
    build_probes,
    probe_all,
)
from fincilia_platform.settings import (
    GATED_CAPABILITIES,
    ApiSettings,
    Settings,
    WorkerSettings,
    get_api_settings,
    get_settings,
    get_worker_settings,
)

__all__ = [
    "CacheProbe", "DatabaseProbe", "ObjectStoreProbe", "Probe", "ProbeResult",
    "build_probes", "probe_all", "GATED_CAPABILITIES", "Settings", "get_settings",
    "ApiSettings", "WorkerSettings", "get_api_settings", "get_worker_settings",
]

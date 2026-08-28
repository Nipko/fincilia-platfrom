"""Plataforma compartida: configuración, sondas y observabilidad.

Lo consumen `apps/api` y `workers/*`. Vive aqui y no en cada servicio porque dos
copias de las mismas reglas fail-closed se separan en cuanto alguien toca una.

Los exports son perezosos. Importar sólo ``observability`` no debe cargar boto3,
psycopg, Valkey y pydantic: ampliar la superficie de arranque de una herramienta
offline hace que un formatter de logs dependa accidentalmente de la red y la base.
"""

from importlib import import_module

__all__ = [
    "CacheProbe", "DatabaseProbe", "ObjectStoreProbe", "Probe", "ProbeResult",
    "build_probes", "probe_all", "GATED_CAPABILITIES", "Settings", "get_settings",
    "ApiSettings", "WorkerSettings", "get_api_settings", "get_worker_settings",
]

_PROBES = frozenset({
    "CacheProbe", "DatabaseProbe", "ObjectStoreProbe", "Probe", "ProbeResult",
    "build_probes", "probe_all",
})
_SETTINGS = frozenset({
    "GATED_CAPABILITIES", "Settings", "get_settings", "ApiSettings",
    "WorkerSettings", "get_api_settings", "get_worker_settings",
})


def __getattr__(name: str):
    if name in _PROBES:
        return getattr(import_module("fincilia_platform.probes"), name)
    if name in _SETTINGS:
        return getattr(import_module("fincilia_platform.settings"), name)
    raise AttributeError(name)

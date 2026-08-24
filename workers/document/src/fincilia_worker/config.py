"""Configuracion del worker: la clase tipada compartida, sin clave de firma.

El worker no emite ni valida tokens, asi que recibir la clave de firma solo
ampliaria su radio de explosion. `WorkerSettings` la rechaza explicitamente.
"""

from fincilia_platform.settings import WorkerSettings
from fincilia_platform.settings import get_worker_settings as load_settings

__all__ = ["WorkerSettings", "load_settings"]

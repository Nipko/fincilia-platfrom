"""Configuracion tipada y exclusiva del dispatcher."""

from fincilia_platform.settings import NotificationWorkerSettings
from fincilia_platform.settings import get_notification_worker_settings as load_settings

__all__ = ["NotificationWorkerSettings", "load_settings"]

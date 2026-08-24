"""Sondas del worker: las mismas que la API, sin duplicar reglas."""

from fincilia_platform.probes import ProbeResult, probe_all

__all__ = ["ProbeResult", "probe_all"]

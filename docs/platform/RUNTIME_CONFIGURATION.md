# Configuración de runtime

Local y CI aceptan solo datos sintéticos. Staging/production, object storage externo,
telemetría externa y AI Gateway permanecen deshabilitados. Los archivos `.env` son locales
y no versionados; el repositorio solo contiene nombres y ejemplos no secretos.

Orden futuro: defaults seguros → env local no versionado → referencia al secret provider →
validación de política. Una variable ausente o inválida falla el arranque; nunca activa una
capacidad por defecto.

Validación: `python -m tools.runtime_config.validate`.

# Configuración de runtime

Local y CI aceptan solo datos sintéticos. Pilot/staging/production, object storage externo,
telemetría externa y AI Gateway permanecen deshabilitados. Los archivos `.env` son locales
y no versionados; el repositorio solo contiene nombres y ejemplos no secretos.

Orden futuro: defaults seguros → env local no versionado → referencia al secret provider →
validación de política. Una variable ausente o inválida falla el arranque; nunca activa una
capacidad por defecto.

`pilot` existe como valor tipado pero permanece deshabilitado en este contrato. No
autoriza datos: exige Secrets Manager, credenciales AWS de workload, identidad nominal
y atestaciones separadas DRG-00/DRG-01 firmadas por una clave KMS asimétrica. El runtime
solo obtiene `kms:Verify`; la capacidad de firma queda fuera de la aplicación.

Validación: `python -m tools.runtime_config.validate`.

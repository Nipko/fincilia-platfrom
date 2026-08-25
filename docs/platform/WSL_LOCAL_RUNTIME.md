# Runtime local persistente en Windows y WSL

| Campo | Valor |
|---|---|
| Tarea | FNC-PLT-009 |
| Estado | Review pending |
| Contrato | `docs/platform/wsl-local-runtime.json` |
| Entry point | `infra/local/fincilia-local.ps1` |
| Datos | Exclusivamente sintéticos |
| Revisión pendiente | Platform/SRE, Security, Developer Experience |

## Problema demostrado

Docker Engine corre dentro de Ubuntu/WSL, sin Docker Desktop. Los comandos
`wsl docker ...` funcionaban mientras `wsl.exe` estaba activo, pero al terminar la
última invocación Windows detenía la distribución. PostgreSQL, Valkey, MinIO, API,
worker y web terminaban simultáneamente con código 255. No hubo OOM, falta de disco
ni error específico de una aplicación; el journal mostraba arranques nuevos y
cierres no limpios de systemd.

Un `sleep infinity` ejecutado mediante un `wsl.exe` oculto mantuvo Ubuntu, Docker y
los seis servicios saludables más allá del ciclo de caída. El wrapper convierte
esa dependencia de estación de trabajo en lifecycle explícito y reversible.

## Diseño

`up` crea un único keepalive, espera hasta 45 segundos a que Docker responda y
ejecuta `infra/local/up.sh`. El script existente conserva el orden obligatorio:
build, detener consumidores antiguos, infraestructura, migración, semilla sintética,
aplicaciones y readiness de API/esquema.

El estado vive fuera del repositorio en `LocalApplicationData/Fincilia` y contiene
solo PID, distribución, proyecto e instante de inicio. Antes de reutilizarlo se
comprueban el ejecutable y la línea de comando del PID; un PID reciclado no obtiene
autoridad sobre otro proceso.

`status` reduce la salida a servicio, estado, salud y puertos. No devuelve labels,
entorno, credenciales ni el inventario Docker global. `down` está fijado al compose
y proyecto de Fincilia, conserva volúmenes y detiene solamente el proceso registrado.

## Límites de seguridad

- Distribución con patrón cerrado y argumentos separados; no hay comando formado
  con entrada del usuario.
- Sin instalación, actualización o edición de `.wslconfig`/`wsl.conf`.
- Sin cierre global de WSL, terminación de distribuciones, prune o borrado de
  volúmenes.
- Lock atómico fuera del repo para impedir dos lifecycles mutadores concurrentes.
- Los fallos no se redondean: dependencia ausente sale 3 y lifecycle fallido sale 1.

## Decisión UD-PLT-CLI-WSL

La CLI Python sigue siendo portable y no cruza WSL implícitamente. Windows usa un
entrypoint específico, contractualmente acotado y visible en la documentación. La
decisión evita ampliar `ALLOWED_EXTERNAL` con un ejecutor genérico y permite que CI
y Linux sigan usando Docker de forma nativa.

Esta decisión no mueve S1-READY ni sustituye la revisión independiente de
Platform/SRE y Security.

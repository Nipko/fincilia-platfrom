---
task_id: FNC-PLT-009
status: REVIEW_PENDING
base_sha: 63484e4
implementation_sha: 2ef810f
integration_sha: be192d9
data_ceiling: synthetic_only
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Platform/SRE, Security, Developer Experience]
---

# Handoff FNC-PLT-009

## Resultado entregado

El stack local de Fincilia permanece activo en Windows aunque termine el comando
PowerShell que lo levanto. `infra/local/fincilia-local.ps1` administra `doctor`,
`up`, `status` y `down`; conserva la distribucion Ubuntu mediante un `wsl.exe`
oculto y opera unicamente el compose/proyecto allowlisted de Fincilia.

La plataforma se entrega corriendo en <http://127.0.0.1:53000>, con API, web,
worker, PostgreSQL, Valkey y MinIO saludables y datos exclusivamente sinteticos.

## Causa demostrada

- Docker Engine 29.7.2 corre dentro de Ubuntu/WSL con systemd. No existe
  `.wslconfig` ni Docker Desktop manteniendo el backend.
- Al finalizar la ultima invocacion `wsl.exe`, Ubuntu se detenia. La siguiente
  llamada mostraba uptime cercano a cero, un nuevo `dockerd` y journals marcados
  como cierre no limpio. Los seis contenedores quedaban con exit 255.
- API/web no estaban OOM-killed; habia aproximadamente 29 GiB disponibles y mas
  de 800 GiB libres. La caida simultanea era lifecycle de WSL, no una excepcion
  de aplicacion.
- Un proceso Windows `wsl.exe --distribution Ubuntu --exec sleep infinity`
  mantuvo Docker y los seis contenedores sanos mas alla del ciclo reproducido.

## Implementacion y limites

- `Start-Process` usa `WindowStyle Hidden`. El estado fuera del repo contiene solo
  PID, distribucion, proyecto e instante.
- Antes de reutilizar o detener el PID se comprueban ejecutable y linea de comando;
  un PID reciclado o manipulado se descarta sin matar el proceso ajeno.
- La distribucion usa un patron cerrado, el repo viaja por `wsl.exe --cd` y los
  comandos son argv fijos. `up` reutiliza el lifecycle revisado `infra/local/up.sh`.
- `status` muestra solo servicio, estado, salud y puertos; omite labels, entorno y
  metadatos Docker libres.
- `down` conserva volumenes, no hace prune, no termina WSL ni otras distribuciones
  y detiene solo el keepalive registrado. Un lock atomico serializa up/down.
- La CLI Python sigue portable; `UD-PLT-CLI-WSL` se resuelve con este entrypoint
  explicito, no ampliando el ejecutor generico.

## Evidencia ejecutada

- PowerShell parser: script valido, sin errores sintacticos.
- `tools.wsl_runtime`: 11 pruebas adversariales, OK. Mutaciones cubren proyecto,
  compose, borrado, cierre global, PID, ventana, estado, output, espera y gate.
- `tools.dev_cli`, `tools.local_stack` y `tools.wsl_runtime`: 126 pruebas, OK.
- Validadores de WSL y stack local: OK, cero hallazgos.
- Lifecycle real: `doctor` OK; `status` detenido sale fail-closed; `up` aplico
  V0001-V0022 sin checksum mutado, sembro solo fixtures sinteticos y dejo 6/6
  servicios healthy.
- Persistencia: 45 segundos despues de terminar `up`, keepalive y 6/6 servicios
  seguian activos. Antes y despues de `down` + segundo `up`, PostgreSQL conservo
  11 empresas sinteticas. `down` dejo status detenido y luego el segundo `up`
  devolvio web HTTP 200 y API `ready`.
- Quality gate sobre el indice del commit funcional: OK, cero hallazgos.

## Hallazgos de ejecucion

1. Mantener Docker como servicio systemd no basta en esta configuracion de WSL:
   la distribucion necesita un proceso Windows vivo.
2. Invocar repetidamente `wsl docker ...` durante el arranque podia reiniciar la
   distribucion y producir `WaitForBootProcess`; un solo keepalive elimina la carrera.
3. La salida cruda de `docker compose ps --format json` incluia labels internas.
   Se redujo antes de integrar para no convertir status en fuga de configuracion.
4. `down` retiro contenedores y redes del proyecto, pero las 11 empresas sinteticas
   sobrevivieron en el volumen PostgreSQL y reaparecieron tras `up`.

## Revision pendiente

Platform/SRE debe revisar lifecycle y recuperacion; Security, argv/PID, limites
destructivos y minimizacion; Developer Experience, uso y diagnosticos. El
implementador y `FOUNDER-01` no cuentan como revisores independientes. Esto no
mueve S1-READY, DRG-00 o DRG-01 y no instala ni actualiza componentes del host.

## Rollback

Antes de revertir, ejecutar `.\infra\local\fincilia-local.ps1 down` para retirar
el stack y el keepalive conservando volumenes. Luego revertir consumidor/docs,
validador/contrato y entrypoint. No borrar el directorio de Docker, volúmenes ni
la distribucion WSL.

## Rutas liberadas

Entry point y README local, contrato/documentacion/validador WSL, registro de la
CLI de desarrollo, CI y documentos de implementacion FNC-PLT-009.

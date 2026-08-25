# Entorno local Fincilia

Stack completo de desarrollo con PostgreSQL 17, Valkey, MinIO, API, worker y
plataforma web. Solo admite datos sintéticos y todos los puertos publicados se
ligan a `127.0.0.1`.

## Windows con Docker Engine dentro de WSL

Desde PowerShell, en la raíz del repositorio:

```powershell
.\infra\local\fincilia-local.ps1 doctor
.\infra\local\fincilia-local.ps1 up
.\infra\local\fincilia-local.ps1 status
.\infra\local\fincilia-local.ps1 down
```

`up` abre un proceso `wsl.exe` oculto que mantiene Ubuntu activo, espera Docker,
construye las imágenes, aplica migraciones verificadas, actualiza la semilla
sintética y espera la salud de los seis servicios. Al cerrar PowerShell el stack
continúa activo.

`down` ejecuta únicamente `docker compose down` sobre `fincilia-local`, conserva
los volúmenes y detiene solo el keepalive registrado por Fincilia. No apaga WSL
globalmente ni toca otras distribuciones o proyectos.

La web queda en <http://127.0.0.1:53000> y la documentación local de la API en
<http://127.0.0.1:58080/docs>. Usuarios y credenciales exclusivamente sintéticos
están documentados en `docs/platform/LOCAL_DEVELOPMENT.md`.

## Linux o una terminal WSL que permanecerá abierta

```sh
sh infra/local/up.sh
```

Cuando Docker está instalado dentro de WSL y no existe Docker Desktop, cerrar el
último proceso WSL puede apagar la distribución y terminar los contenedores con
código 255. El wrapper PowerShell evita depender de una terminal interactiva.

## Datos y recuperación

- PostgreSQL y MinIO usan volúmenes nombrados; `down` no los borra.
- Valkey es efímero y nunca fuente de verdad financiera.
- Un estado de keepalive obsoleto se valida contra PID, ejecutable y línea de
  comando antes de reutilizarse; `up` lo reemplaza de forma segura.
- Para un diagnóstico estructurado use `status`; no expone etiquetas, entorno ni
  configuración completa de los contenedores.

La eliminación deliberada de volúmenes es una operación distinta y no forma
parte del wrapper. No utilice documentos financieros reales mientras DRG-00 siga
cerrado.

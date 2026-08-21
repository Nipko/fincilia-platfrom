# FNC-PLT-001 — walking spike descartable

Este directorio valida el stack candidato; no es la base del producto. Solo contiene datos sintéticos y puede eliminarse completo sin migración.

## Qué demuestra

- NestJS/TypeScript recibe una solicitud con `subject` sintético y verifica el `company` en servidor.
- PostgreSQL 17 aplica `FORCE ROW LEVEL SECURITY` con contexto transaccional `SET LOCAL`.
- El registro de dominio y el evento outbox se confirman o revierten juntos.
- Un worker Python procesa un job sintético, emite un manifiesto y rechaza reusar una clave con otro contenido.

## Requisitos

- Docker Engine y Compose dentro de WSL.
- Node.js 22 y npm 11 en Windows.
- Python 3.12 en WSL o Python 3.11+ equivalente.

## Ejecutar

Desde PowerShell, en la raíz del repositorio:

```powershell
wsl -d Ubuntu -- bash -lc "cd '/mnt/c/Users/USER/Desktop/Projects/knowledge-app/spikes/FNC-PLT-001' && docker compose up -d --wait"
wsl -d Ubuntu -- bash -lc "cd '/mnt/c/Users/USER/Desktop/Projects/knowledge-app/spikes/FNC-PLT-001' && docker compose --profile test run --rm api-test"
wsl -d Ubuntu -- bash -lc "cd '/mnt/c/Users/USER/Desktop/Projects/knowledge-app/spikes/FNC-PLT-001/worker' && python3 -m unittest -v"
```

El test de API se ejecuta dentro de la red de Docker porque el daemon vive en WSL y el puerto de PostgreSQL permanece ligado al loopback Linux. Para una ejecución manual desde WSL:

```bash
docker compose exec postgres psql -U postgres -d fincilia_spike
```

Los UUID sintéticos precargados están documentados en `db/init/001_init.sql`.

## Limpiar completamente

```powershell
wsl -d Ubuntu -- bash -lc "cd '/mnt/c/Users/USER/Desktop/Projects/knowledge-app/spikes/FNC-PLT-001' && docker compose down --volumes --remove-orphans"
```

Las contraseñas del Compose son marcadores locales deliberadamente no secretos. Este entorno nunca admite datos reales.

---
task: FNC-PLT-002
status: REVIEW_PENDING
base_sha: 380ad9e
implementer: Integration Steward
data_used: synthetic_only
human_acceptance: pending
---

# Handoff FNC-PLT-002

## Entrega

- Compose local mínimo con PostgreSQL 17 fijado por digest.
- Puerto loopback, red interna, healthcheck, volumen nombrado y mounts read-only.
- Bootstrap sintético y rol de aplicación sin privilegios administrativos/RLS bypass.
- Lifecycle real de arranque limpio, reinicio, stop/start, persistencia y purga.
- Validador estático con mutaciones negativas y job CI independiente.

## Verificación

```powershell
python -m tools.local_stack.validate
python -m unittest tools.local_stack.test_validate -v
wsl -d Ubuntu -- bash -lc "cd '/mnt/c/Users/USER/Desktop/Projects/knowledge-app/infra/local' && docker compose config --quiet"
```

La secuencia runtime completa está documentada en `infra/local/README.md` y automatizada en CI.

Resultado local observado: 9/9 pruebas estáticas, Compose config, lifecycle inicial,
persistencia tras restart, persistencia tras stop/start y cleanup de volumen pasan.

## Revisión requerida

- Platform: lifecycle, ergonomía WSL, upgrades y observabilidad futura.
- Security: credenciales desechables, red, privilegios y mounts.
- Architecture: contenedores mínimos y criterios de activación de stores diferidos.

## Límites

El SQL bootstrap es infraestructura de prueba, no una migración productiva. Las credenciales
por defecto son públicas/locales y nunca deben reutilizarse. Object storage, Temporal,
Valkey y analytics permanecen diferidos y no se sustituyen por esta base.

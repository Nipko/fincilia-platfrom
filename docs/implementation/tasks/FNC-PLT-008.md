---
task: FNC-PLT-008
title: Stack local de producto ejecutable
status: review_pending
implementer: Claude (principal dev)
base_sha: 9edfd02
integration_sha: see_git_commit_containing_this_task
gate: S1-READY
data_ceiling: synthetic_only
independent_reviewers: [Platform, Security, QA]
---

# Resultado esperado

Un solo comando levanta el stack local completo y los cinco servicios quedan healthy:
PostgreSQL, Valkey, object storage S3-compatible, API FastAPI y worker de documentos.

Incluye el paquete de contratos compartido, la configuración tipada fail-closed por
servicio, las zonas de evidencia y los endpoints de salud y diagnóstico.

# Rutas reservadas

- `apps/api/**`
- `workers/document/**`
- `packages/contracts/**`
- `packages/platform/**`
- `infra/local/**`
- `docs/platform/LOCAL_DEVELOPMENT.md`
- `docs/implementation/tasks/FNC-PLT-008.md`
- `docs/implementation/handoffs/FNC-PLT-008.md`

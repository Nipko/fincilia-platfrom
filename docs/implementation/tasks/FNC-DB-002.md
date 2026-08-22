---
task: FNC-DB-002
title: Spike ejecutable de invariantes de migración SQL-first
status: review_pending
implementer: Claude (external principal dev)
base_sha: 48b21d1
integration_sha: see_git_commit_containing_this_task
gate: ADR-002-MIGRATIONS
data_ceiling: synthetic_only
independent_reviewers: [Database Migration Owner, Architecture, Security, QA]
---

# Resultado esperado

Probar en PostgreSQL efímero los invariantes blank, replay, checksum, concurrencia,
atomicidad y separación migrator/runtime. Es un spike reversible y no selecciona ni
promueve herramienta de migraciones a producto.

# Rutas reservadas

- `docs/database/MIGRATION_SPIKE.md`
- `docs/database/migration-spike.json`
- `spikes/FNC-DB-002/**`
- `tools/migration_spike/**`
- `docs/implementation/handoffs/FNC-DB-002.md`

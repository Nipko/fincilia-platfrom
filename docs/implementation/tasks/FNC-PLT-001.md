---
id: FNC-PLT-001
title: Spike y decisión del stack inicial
epic: FNC-EP-006
phase: F0
iteration: E0
type: spike
status: review_pending
priority: P0
accountable_owner: UNASSIGNED (human acceptance pending)
implementer: Integration Steward
agent_lane: A4
independent_reviewer: Architecture
plan_refs: [§20, §52]
adr_refs: [ADR-001, ADR-002, ADR-007]
dependencies: [FNC-GOV-002]
gate: S1-READY
allowed_data: synthetic
base_sha: f621236
file_scope: [spikes/FNC-PLT-001, docs/adr/ADR-001-modular-monolith-workers.md, docs/adr/ADR-002-postgresql-rls.md, docs/implementation/evidence/FNC-PLT-001, docs/implementation/tasks/FNC-PLT-001.md]
forbidden_scope: [production, real-data, lockfiles-without-reservation]
---

# Resultado esperado

Confirmar o refutar NestJS/TypeScript para dominio y Python para workers mediante un walking spike descartable.

# Modalidad de ejecución

- Spike aislado y eliminable bajo `spikes/FNC-PLT-001/`; no es código de producto.
- PostgreSQL local en Docker, ligado a `127.0.0.1` y con volumen descartable.
- Credenciales y registros exclusivamente sintéticos.
- El Integration Steward integra manifiestos, lockfile, Compose y ADR; la aceptación arquitectónica sigue requiriendo owner humano.

# Criterios de aceptación

- Un request crea contexto de company verificado y transacción.
- PostgreSQL demuestra FORCE RLS y SET LOCAL sin fuga de pool.
- Un cambio de dominio y outbox son atómicos.
- Un worker sintético consume un job idempotente y devuelve manifiesto.
- Se comparan complejidad, tipos, tooling, testing, observabilidad y equipo.
- ADR-001 y ADR-002 quedan listos para decisión humana.
- El spike se elimina o queda aislado; no se presenta como producto.

# Pruebas

TST-RLS-001, TST-RLS-002 y TST-OUT-001 con datos sintéticos.

---
task: FNC-DB-004
title: Spike PostgreSQL de reclamo concurrente, outbox y lease expirado
status: proposed
implementer: UNASSIGNED
base_sha: 81f7dd9
integration_sha: pending
gate: S1-READY
data_ceiling: synthetic_only
independent_reviewers: [Architecture, Security, QA]
---

# Resultado esperado

Probar contra PostgreSQL real las tres invariantes de idempotencia que no son
demostrables con lógica pura y que `FNC-DOM-007` dejó explícitamente fuera:

- `TST-IDEM-001` — dos reclamos concurrentes del mismo trabajo producen una sola
  ejecución, mediante inserción atómica o compare-and-set.
- `TST-IDEM-004` — una caída después del commit de dominio y antes de la entrega no
  pierde el efecto: el outbox lo vuelve a entregar.
- `TST-IDEM-005` — un worker que despierta tras expirar su lease no puede escribir,
  porque su token de fencing es viejo.

El patrón de laboratorio ya está validado en `spikes/FNC-DB-002`: Compose con proyecto
propio, imagen fijada por digest, sin puerto publicado, red interna y limpieza confinada.

# Rutas reservadas

- `spikes/FNC-DB-004/**`
- `tools/concurrency_spike/**`
- `docs/database/CONCURRENCY_SPIKE.md`
- `docs/implementation/tasks/FNC-DB-004.md`
- `docs/implementation/handoffs/FNC-DB-004.md`

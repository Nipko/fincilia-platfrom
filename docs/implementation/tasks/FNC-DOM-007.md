---
task: FNC-DOM-007
title: Especificación ejecutable de identidad, idempotencia y dedupe
status: review_pending
implementer: Claude (principal dev)
base_sha: 81f7dd9
integration_sha: see_git_commit_containing_this_task
gate: S1-READY
data_ceiling: synthetic_only
independent_reviewers: [Architecture, Security, QA]
---

# Resultado esperado

Materializar nueve de las doce pruebas que `docs/domain/idempotency-dedupe.json` declara
obligatorias: `TST-DED-001` a `TST-DED-005`, `TST-IDEM-002`, `TST-IDEM-003`,
`TST-IDEM-006` y `TST-IDEM-007`.

Las tres restantes —`TST-IDEM-001` reclamo concurrente, `TST-IDEM-004` caída tras commit
de dominio y `TST-IDEM-005` worker con lease expirado— exigen PostgreSQL real y se
implementan en `FNC-DB-004`. No se simulan aquí.

# Rutas reservadas

- `tools/dedupe_engine/**`
- `docs/domain/DEDUPE_ENGINE.md`
- `docs/implementation/tasks/FNC-DOM-007.md`
- `docs/implementation/handoffs/FNC-DOM-007.md`

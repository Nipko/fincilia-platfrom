---
task: FNC-DOM-006
title: Especificación ejecutable de completitud y conciliación de saldos
status: review_pending
implementer: Claude (principal dev)
base_sha: 81f7dd9
integration_sha: see_git_commit_containing_this_task
gate: S1-READY
data_ceiling: synthetic_only
independent_reviewers: [Accounting, Architecture, QA]
---

# Resultado esperado

Materializar las seis pruebas que `docs/domain/completeness-balances.json` declara
obligatorias y que seguían sin implementación: `TST-CMP-001`, `TST-CMP-002`,
`TST-BAL-001`, `TST-BAL-002`, `TST-EXC-001` y `TST-CLOSE-001`.

Es una especificación ejecutable del contrato, no la implementación de producto: vive
bajo `tools/` porque `product_code_allowed` sigue en `false` hasta S1-READY.

# Rutas reservadas

- `tools/completeness_engine/**`
- `tests/golden/completeness/**`
- `docs/domain/COMPLETENESS_ENGINE.md`
- `docs/implementation/tasks/FNC-DOM-006.md`
- `docs/implementation/handoffs/FNC-DOM-006.md`

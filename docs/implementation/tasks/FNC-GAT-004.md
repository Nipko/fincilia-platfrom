---
task: FNC-GAT-004
title: Relevancia explícita de contradicciones en el agregador S1
status: review_pending
implementer: Claude (principal dev)
base_sha: 81f7dd9
integration_sha: see_git_commit_containing_this_task
gate: S1-READY
data_ceiling: synthetic_only
independent_reviewers: [Architecture, Security, QA]
---

# Resultado esperado

El agregador de readiness debe decidir qué contradicción bloquea a partir de una
declaración explícita del contrato, no de qué requisitos existan por casualidad. Una
contradicción que no bloquea S1-READY no puede desaparecer: o está enrutada a un owner
nominal y a su propio gate, o bloquea.

# Problema observado

En la base `81f7dd9`, `relevant_gates` se derivaba de los requisitos de tipo `gate`. Como
la integración retiró esos requisitos, el conjunto quedó reducido al gate objetivo y las
dos contradicciones reales sobre el owner de `DRG-00` y `DRG-01` pasaron a reportarse sin
bloquear nada, sin que nadie lo hubiera decidido.

# Rutas reservadas

- `docs/implementation/s1-readiness.json`
- `docs/implementation/S1_READINESS_REPORT.md`
- `tools/s1_readiness/**`
- `docs/implementation/tasks/FNC-GAT-004.md`
- `docs/implementation/handoffs/FNC-GAT-004.md`

---
task: FNC-SUP-001
title: Baseline ejecutable de cadena de suministro
status: review_pending
implementer: Claude (external principal dev)
base_sha: 48b21d1
integration_sha: see_git_commit_containing_this_task
gate: DRG-00
data_ceiling: synthetic_only
independent_reviewers: [Security, Platform, QA]
---

# Resultado esperado

Construir un inventario y validador offline de acciones, imágenes, runtimes y locks que
detecte referencias flotantes, fuentes no inventariadas y afirmaciones de procedencia no
demostradas. El artefacto no firma builds ni declara cerrado TM-005.

# Rutas reservadas

- `docs/security/SUPPLY_CHAIN_BASELINE.md`
- `docs/security/supply-chain.json`
- `tools/supply_chain/**`
- `docs/implementation/handoffs/FNC-SUP-001.md`

## Integración correctiva 2026-08-25

El Integration Steward amplió las rutas a `.github/dependabot.yml`,
`docs/implementation/s1-readiness.json`, `CURRENT_PHASE.md` y el handoff R1. Se
eliminó el falso alcance `.next`, se completó la vigilancia de updates y se añadió
evaluación explícita por gate. Los cuatro gaps de procedencia conservan gate DRG-00;
no se rebajaron ni se marcaron satisfechos.

---
task: FNC-SUP-001
title: Baseline ejecutable de cadena de suministro
status: claimed
implementer: Claude (external principal dev)
base_sha: 48b21d1
integration_sha: pending_integration_steward
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

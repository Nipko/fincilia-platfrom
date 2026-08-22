---
task: FNC-PLT-007
title: CLI segura de desarrollo y diagnóstico local
status: claimed
implementer: Claude (external principal dev)
base_sha: 48b21d1
integration_sha: pending_integration_steward
gate: S1-READY
data_ceiling: synthetic_only
independent_reviewers: [Platform, Security, Developer Experience, QA]
---

# Resultado esperado

Crear una CLI Python offline para doctor, validación, pruebas y ciclo de vida local con
argv allowlisted, salida JSON estable y cero borrado de volúmenes. Debe orquestar sin
convertirse en una segunda fuente de gates o secretos.

# Rutas reservadas

- `docs/platform/DEVELOPER_CLI.md`
- `docs/platform/developer-cli.json`
- `tools/dev_cli/**`
- `docs/implementation/handoffs/FNC-PLT-007.md`

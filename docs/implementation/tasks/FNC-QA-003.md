---
task: FNC-QA-003
title: Golden harness determinista y adjudicado
status: review_pending
implementer: Claude (external principal dev)
base_sha: c227f1c
integration_sha: see_git_commit_containing_this_task
gate: S1-READY
data_ceiling: synthetic_only
independent_reviewers: [QA, Data, Accounting, Security]
---

# Resultado esperado

Implementar un harness local/CI que ejecute suites adjudicadas contra versiones exactas,
verifique resultados y manifiestos, produzca evidencia determinista y falle ante drift,
tampering, comandos no permitidos o datos no sintéticos.

## Rutas reservadas

- `docs/testing/GOLDEN_HARNESS.md`
- `docs/testing/golden-harness.json`
- `tools/golden_harness/**`
- `tests/golden/harness/**`
- `docs/implementation/handoffs/FNC-QA-003.md`

## Criterios

1. Registro estricto de casos, comando argv sin shell, timeout, cwd, inputs, expectativas y owner.
2. Solo módulos/fixtures allowlisted; cero red, secretos, datos reales o rutas externas.
3. Resultados comparan exit code y salida estructurada; el digest excluye métricas no deterministas.
4. Manifest registra registry hash, input hashes, runtime y output digest sin versiones flotantes.
5. Replay idéntico conserva digest; cambio de input/contrato produce clave nueva.
6. Ausencia, hash distinto, caso no inventariado, skip o actualización silenciosa fallan.
7. El harness no reemplaza validadores, no autoaprueba expected outputs y no publica estado financiero.
8. CLI `list`, `verify` y `run`; tests positivos/negativos offline con biblioteca estándar.

---
task: FNC-QA-004
title: Catálogo de pruebas ejecutable y reconciliación de cobertura
status: review_pending
implementer: Claude (external principal dev) + Integration Steward
base_sha: 6e23c04
integration_sha: see_git_commit_containing_this_task
gate: S1-READY
data_ceiling: synthetic_only
independent_reviewers: [QA, Architecture, Accounting, Security]
---

# Resultado esperado

Construir un modelo ejecutable que descubra y clasifique los IDs de prueba del
repositorio, distinga requisitos contractuales de especificaciones runtime planeadas y
detecte drift sin mantener una segunda lista manual.

## Rutas reservadas

- `docs/testing/TEST_CATALOG_MODEL.md`
- `docs/testing/test-catalog-model.json`
- `tools/test_catalog/**`
- `docs/implementation/handoffs/FNC-QA-004.md`

## Criterios

1. Descubrimiento dinámico de IDs desde contratos JSON, Markdown, tests Python y manifests.
2. Proveniencia por ID, categoría, estado, owner, gate y evidencia esperada.
3. Los contractuales ausentes del catálogo son drift; los runtime planeados sin contrato son backlog, no falso drift.
4. Duplicados incompatibles, IDs mal formados, fuentes desconocidas y referencias circulares fallan.
5. La proyección propuesta del catálogo se genera como diff/datos, pero nunca edita `TEST_CATALOG.md`.
6. Validador estricto, offline, determinista, con entradas inyectables para mutaciones.
7. Pruebas positivas y negativas que demuestren que cada regla crítica muerde.

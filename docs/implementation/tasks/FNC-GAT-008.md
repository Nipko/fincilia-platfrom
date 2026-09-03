---
id: FNC-GAT-008
title: Estado funcional ejecutable de plataforma web
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 6ff3d64
gate: none
gate_effect: evidence_only
data_ceiling: synthetic_only
independent_reviewers: [Product, Accounting, QA]
---

# Resultado

Un inventario ponderado distingue completitud de implementacion, evidencia UAT
sintetica y operabilidad de produccion. El calculo es reproducible y no presenta
un porcentaje de codigo como autorizacion de datos, exactitud contable real o GA.

# Rutas reservadas

- `docs/product/web-functional-status.json` y su informe.
- `tools/web_functional_status/**`.
- ficha, handoff, backlog, fase y trazabilidad por Integration Steward.

# Criterios de aceptacion

1. Los pesos funcionales suman exactamente 100 y cada dominio tiene evidencia.
2. Los factores de calculo son publicos, discretos y no se infieren de lenguaje.
3. Toda evidencia es una ruta canonica existente dentro del repositorio.
4. Mobile queda explicitamente fuera del denominador.
5. Ningun estado real o productivo puede declararse mientras sus gates sigan
   cerrados.
6. El informe separa funcionalidad construida de trabajo operativo pendiente.

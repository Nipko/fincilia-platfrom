---
task: FNC-QA-005
title: Arnés determinista de mutaciones para validadores
status: claimed
implementer: Claude (external principal dev)
base_sha: 6e23c04
integration_sha: pending_integration_steward
gate: S1-READY
data_ceiling: synthetic_only
independent_reviewers: [QA, Security, Architecture]
---

# Resultado esperado

Implementar mutaciones declarativas y reproducibles sobre copias temporales para probar
que los validadores fallan ante debilitamientos críticos, sin escribir sobre contratos
del repositorio ni convertir mutation score en una aprobación automática.

## Rutas reservadas

- `docs/testing/MUTATION_HARNESS.md`
- `docs/testing/mutation-harness.json`
- `tools/mutation_harness/**`
- `tests/golden/mutations/**`
- `docs/implementation/handoffs/FNC-QA-005.md`

## Criterios

1. Mutaciones allowlisted, declarativas, con target, precondición, cambio y oráculo explícitos.
2. Todo se ejecuta en copia temporal; hashes prueban que el árbol fuente no cambió.
3. Cada control protegido tiene mutación independiente; una regla redundante no cuenta dos veces.
4. Survivor crítico falla el comando y se reporta con owner, riesgo, gate y evidencia.
5. Timeout, salida acotada, entorno mínimo, cero shell, red, secretos o rutas externas.
6. Sin umbral global inventado; cobertura y survivors se informan por riesgo/control.
7. CLI de `list`, `verify` y `run`, más pruebas positivas/negativas con biblioteca estándar.

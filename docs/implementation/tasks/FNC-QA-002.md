---
task: FNC-QA-002
title: Estrategia integral de pruebas ejecutable
status: claimed
implementer: Claude (external principal dev)
base_sha: c227f1c
integration_sha: pending_integration_steward
gate: S1-READY
data_ceiling: synthetic_only
independent_reviewers: [QA, Architecture, Security, Accounting]
---

# Resultado esperado

Convertir el seed `TEST_STRATEGY.md` en un contrato ejecutable que conecte riesgo,
requisito, capa de prueba, caso, evidencia, owner, reviewer y gate sin inflar cobertura
ni permitir que skips, flakes o promedios oculten defectos financieros.

## Rutas reservadas

- `docs/testing/TEST_STRATEGY.md`
- `docs/testing/test-strategy.json`
- `tools/quality_strategy/**`
- `docs/implementation/handoffs/FNC-QA-002.md`

## Criterios

1. Capas unit/property/contract/integration/golden/security/E2E/usability están delimitadas.
2. Riesgos altos/críticos y requisitos trazan a pruebas ejecutables y evidencia.
3. IDs se extraen dinámicamente de contratos y catálogo; no hay listas que simulen cobertura.
4. Flaky, skip, quarantine, retry y waiver fallan cerrado en controles financieros/seguridad.
5. Evidencia registra versiones, comando, resultado, hashes y clasificación sintética.
6. Cobertura estructural no se confunde con exactitud contable ni calidad del modelo.
7. Performance, accesibilidad, restore, RLS, privacidad e IA tienen gates explícitos sin inventar umbrales pendientes.
8. Validador y pruebas negativas operan offline con biblioteca estándar.

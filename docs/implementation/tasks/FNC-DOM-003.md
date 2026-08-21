---
task: FNC-DOM-003
title: Completitud, balances y reconciliation statement ejecutables
status: review_pending
implementer: Integration Steward
base_sha: 6fc947e
gate: S1-READY
data_ceiling: synthetic_only
---

# Resultado esperado

Definir el contrato contable ejecutable que separa recepción, completitud de fuentes, conciliación de movimientos y conciliación de saldos. `unknown` nunca puede convertirse en completo por ausencia de controles.

## Rutas permitidas

- `docs/domain/COMPLETENESS_BALANCES.md`
- `docs/domain/completeness-balances.json`
- `tools/completeness_model/**`
- `docs/implementation/handoffs/FNC-DOM-003.md`
- Ownership arquitectónico, CI y archivos centrales solo para integración.

## Dependencias

- FNC-DOM-002 y ADR-014.
- FNC-DOM-004/005 completarán dedupe, matching y linaje.
- Accounting debe aceptar fórmula, materialidad y excepciones.

## Criterios de aceptación

1. Controles de fuente/cuenta/periodo y algoritmo de estado son deterministas.
2. La falta de control produce `unknown`, nunca `verified`.
3. `partial`, `mismatch`, `unknown` y `unverified` bloquean resultados certificados.
4. Excepciones exigen alcance, razón, owner, aprobador independiente y expiración.
5. Statement usa decimal exacto, una moneda y diferencia no explicada explícita.
6. Balanced exige diferencia exactamente cero; aceptar diferencia no la renombra como balanced.
7. Validador, pruebas y CI pasan solo con datos sintéticos.

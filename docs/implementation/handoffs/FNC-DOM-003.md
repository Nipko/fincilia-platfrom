---
task: FNC-DOM-003
status: REVIEW_PENDING
base_sha: 6fc947e
implementer: Integration Steward
data_used: synthetic_only
human_acceptance: pending
---

# Handoff FNC-DOM-003

## Entrega

- Contrato que separa recepción, completitud, matching y conciliación de saldos.
- Doce controles por source/account/period: conteos, totales, saldos, continuidad, periodo, páginas, secuencia, provenance, moneda y cuenta.
- Derivación fail-closed: mismatch precede unknown; verified solo con todos los controles requeridos en match.
- `not_applicable` solo predeclarado en source expectation versionada con razón.
- Matriz de elegibilidad para verified/mismatch/unknown/accepted_exception; auto-match permanece deshabilitado.
- Account balance alineado al modelo canónico.
- Reconciliation statement con fórmula decimal exacta, una moneda y solo items confirmados.
- Balanced exige diferencia exactamente cero; una diferencia aceptada conserva estado `exception_accepted`.
- Reconciling item con lado explícito, importe positivo, evidencia, SoD y reversión append-only.
- Excepción con scope, razón, owner, aprobador independiente, materialidad, vigencia, evidencia y auditoría.
- Nueve condiciones acumulativas de close readiness.
- Ownership arquitectónico sincronizado para assessment, control result, statement e item.
- Validador Python sin dependencias y 23 pruebas de mutación.

## Verificación

```powershell
python -m tools.completeness_model.validate
python -m unittest tools.completeness_model.test_validate -v
python -m unittest discover -s tools -p "test_*.py"
python -m tools.architecture_model.validate
python -m tools.canonical_model.validate
python -m tools.quality_gate.cli
```

Resultado observado antes de integración:

- Modelo completitud/saldos: PASS, 0 errores.
- Pruebas específicas: 23/23 PASS.
- Suite CI Python integrada, excluyendo el handoff externo aún no indexado: 95/95 PASS.
- Modelos arquitectónico, canónico, DFD y threat model: PASS.
- Quality gate: PASS, 0 hallazgos; workflow YAML y diff check: PASS.
- Corpus: 5/5 verificado con dos advertencias intencionales de fórmula inerte.
- No se usaron datos reales, red, proveedor o IA externa.

## Decisiones preservadas

- Un artefacto procesado no prueba completitud.
- Un saldo observado no prueba completitud.
- Match coverage no sustituye source completeness.
- Matches de movimientos no sustituyen conciliación de saldos.
- Unknown nunca se transforma en verified por falta de información.
- Excepción no borra el estado base ni habilita auto-match.
- Diferencia aceptada no se etiqueta balanced.
- E0 no habilita auto-match ni cierre productivo.

## Pendientes

- Accounting debe aprobar balance types, fórmula, materialidad, tolerancias y política de excepciones.
- Data Engineering debe mapear controles disponibles por cada source/template real después del gate correspondiente.
- DOM-004 completa matching/dedupe/idempotencia; DOM-005, linaje/releases.
- Close state machine y snapshots requieren revisión Product/Accounting/Security.
- Las entidades son contrato conceptual, no migraciones SQL.

## Rollback

Retirar documento/modelo/tooling/paso CI y restaurar ownership previo. No existen migraciones, despliegues, cierres ni datos reales.

Esta entrega no supera S1-READY ni autoriza DRG-00.

---
task: FNC-DOM-002
status: REVIEW_PENDING
base_sha: 00d9408
implementer: Integration Steward
data_used: synthetic_only
human_acceptance: pending
---

# Handoff FNC-DOM-002

## Entrega

- Documento canónico v0.1 con fronteras sources→evidence→finance.
- Modelo JSON ejecutable con 14 tipos lógicos, enums controlados, 12 invariantes y 20 entidades.
- Ownership sincronizado con el modelo modular para `source_expectation`, `reference_dataset_version`, `artifact_version`, `movement_evidence_link` y `external_reference`.
- Dinero como decimal exacto con representación JSON string; moneda y dirección/débito-crédito explícitos.
- Company scope obligatorio, identidad `(company_id,id)` y FKs compuestas para relaciones company-scoped.
- Separación de observación (`source_record`) y hecho (`money_movement`) mediante `movement_evidence_link`.
- Fechas occurred/posted/value/accounting/settled/issued/due separadas.
- Settlement con componentes brutos, fees, impuestos, retenciones, refunds, ajustes y neto.
- Dedupe fingerprint explícitamente candidate-only y constraints únicos peligrosos rechazados.
- JSONB con schema/size, bytes en object storage y cuentas tokenizadas/last4.
- Reproducibilidad mediante engine release, schema version y lineage state en hechos publicados.
- Validador Python sin dependencias y 20 pruebas de mutación.
- CI ampliado para validar contrato y pruebas.

## Verificación

```powershell
python -m tools.canonical_model.validate
python -m unittest tools.canonical_model.test_validate -v
python -m unittest discover -s tools -p "test_*.py"
python -m tools.architecture_model.validate
python -m tools.quality_gate.cli
```

Resultado observado antes de integración:

- Modelo canónico: PASS, 0 errores.
- Pruebas canónicas: 20/20 PASS.
- Suite Python combinada: 72/72 PASS.
- Modelos de arquitectura, DFD y threat model: PASS, 0 errores.
- Quality gate: PASS, 0 hallazgos; workflow YAML y diff check: PASS.
- Corpus: 5/5 verificado con dos advertencias intencionales de fórmula inerte.
- No se usaron datos reales, red, proveedor externo ni IA externa.

## Decisiones preservadas

- Company permanece estable al cambiar de firma.
- Source record es evidencia, no movimiento.
- Dos movimientos legítimos idénticos pueden coexistir.
- Fecha/monto/dirección/referencia nunca forman unicidad dura.
- Money no usa float.
- Binarios viven en object storage.
- Worker no publica estado financiero canónico.
- Todo hecho publicado exige linaje/release, aunque DOM-005 complete su forma.

## Pendientes y dependencias

- Accounting debe validar precision/scale, rounding y ecuaciones por moneda.
- FNC-DOM-003 completa completeness assessment, account balances y reconciliation statement.
- FNC-DOM-004 materializa dedupe candidates, merge decisions, idempotencia y concurrencia.
- FNC-DOM-005 completa origin locators, overlays, lineage edges y engine release.
- Database Migration Owner debe diseñar constraints SQL y rollback; este JSON no es una migración.
- El índice único parcial de operador primario sigue fuera de este contrato.
- PRV-001/L-01 define retención y borrado de cada entidad/store.
- Owners humanos y revisión Architecture/Accounting/Data/Security siguen pendientes.

## Rollback

Restaurar el seed de `CANONICAL_MODEL.md`, retirar JSON/tooling/paso CI y revertir únicamente las adiciones de ownership conceptual. No existen migraciones, despliegues ni datos reales.

Esta entrega no supera S1-READY ni autoriza DRG-00.

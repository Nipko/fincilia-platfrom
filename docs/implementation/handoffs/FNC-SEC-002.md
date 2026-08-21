---
task: FNC-SEC-002
status: REVIEW_PENDING
base_sha: 0bb360e
implementer: Integration Steward
data_used: synthetic_only
human_acceptance: pending
---

# Handoff FNC-SEC-002

## Entrega

- Threat model STRIDE + abuso de negocio/contable + privacidad.
- Doce activos críticos y 15 escenarios concretos de riesgo.
- Cobertura completa de amenazas DFD T01–T12, flujos F01–F13 y 15 tags obligatorios.
- Score inherente y residual proyectado determinista con bandas baja/media/alta/crítica.
- Tratamiento, owner de rol, revisores independientes, target gate, evidencia y estado abierto por riesgo.
- Riesgos seed preservados: cross-company, pool context, autorización, revocación, archivo/PAN, worker, completitud, dedupe, replay, IA/prompt injection, logs, exports, auditoría, restore y supply chain.
- Validador sin dependencias y 13 pruebas de mutación.
- CI ampliado para comprobar cobertura y prohibir aceptación/cierre automático de riesgos.

## Verificación

```powershell
python -m tools.threat_model.validate
python -m unittest tools.threat_model.test_validate -v
python -m unittest discover -s tools -p "test_*.py"
python -m tools.quality_gate.cli
```

Resultado observado antes de integración:

- Modelo: PASS, 0 errores.
- Pruebas threat model: 13/13 PASS.
- Suite Python combinada: 52/52 PASS.
- Arquitectura modular y DFD: PASS, 0 errores.
- Quality gate: PASS, 0 hallazgos; workflow YAML y diff check: PASS.
- Corpus: 5/5 verificado; solo dos advertencias intencionales de fórmula inerte.
- Todos los paths de evidencia referenciados existen.
- Toda aceptación permanece `pending_human`; todo residual, `projected_not_accepted`.
- No se usaron datos reales, red, proveedor externo ni escáner remoto.

## Riesgos que siguen abiertos

- TM-003 depende de cerrar las tres brechas de integración SEC-001: role/action, principals de servicio/organization y tupla action/resource/purpose.
- TM-005 requiere S-01: detección PAN antes de raw y prueba end-to-end de quarantine.
- TM-007/TM-008 requieren contratos DOM-003/DOM-004 de completitud, balances y dedupe.
- TM-010 queda fuera del camino inicial; L-02/AI Gateway y evals son previos a cualquier IA externa.
- TM-014 requiere L-01 y ensayo restore+tombstones antes de DRG-00.
- TM-015 requiere contrato ejecutable de engine release/ADR-023 y SBOM/provenance.
- Ningún score residual ha sido aceptado por un humano ni medido en producción.

## Revisiones obligatorias

- Security + Architecture: modelo completo y tratamientos.
- Privacy: TM-005, TM-010, TM-011, TM-012 y TM-014.
- Accounting: TM-007 y TM-008.
- Platform: TM-002, TM-006, TM-009, TM-014 y TM-015.

## Rollback

Restaurar el seed de `THREAT_MODEL.md`; retirar JSON, tooling, pruebas, paso CI y este handoff. No existen despliegues, migraciones, aceptaciones ni datos reales.

Esta entrega no supera S1-READY ni autoriza DRG-00.

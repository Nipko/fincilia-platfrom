---
task: FNC-DOM-002
title: Modelo canonico financiero ejecutable v0.1
status: review_pending
implementer: Integration Steward
base_sha: 00d9408
gate: S1-READY
data_ceiling: synthetic_only
---

# Resultado esperado

Definir un contrato ejecutable para fuentes, evidencia estructurada y hechos financieros sin convertir observaciones en movimientos, perder duplicados legítimos ni introducir tipos monetarios ambiguos.

## Rutas permitidas

- `docs/domain/CANONICAL_MODEL.md`
- `docs/domain/canonical-model.json`
- `tools/canonical_model/**`
- `docs/implementation/handoffs/FNC-DOM-002.md`
- `docs/architecture/module-boundaries.json` y documentación C4 solo para sincronizar ownership conceptual.
- `.github/workflows/ci.yml`, `docs/testing/CI_QUALITY_GATE.md`, `CURRENT_PHASE.md` y backlog para integración.

## Dependencias

- FNC-PRD-001, FNC-DAT-001 y FNC-DOM-001 en revisión.
- ADR-003, ADR-005, ADR-014, ADR-015 y ADR-023 aceptados con owners humanos aún pendientes.
- FNC-DOM-003/004/005 ampliarán balances/completitud, dedupe/idempotencia y linaje/releases sin relajar este contrato.

## Criterios de aceptación

1. Entidades, campos, relaciones, ownership y políticas de mutación son verificables.
2. Dinero usa decimal exacto, moneda ISO 4217 y dirección explícita donde aplica.
3. Todo hecho financiero es company-scoped y toda FK financiera es compuesta.
4. `source_record` y `money_movement` permanecen separados y se relacionan por evidencia.
5. Dedupe por fecha/monto/dirección/referencia nunca es unicidad dura.
6. Fecha económica, posting, value y accounting date permanecen distintas.
7. Binarios no entran en PostgreSQL y JSON exige schema/size.
8. Validador, pruebas, arquitectura y CI pasan exclusivamente con datos sintéticos.

# ADR-009 — AI Gateway y prohibiciones

- Status: Accepted
- Date: 2026-08-21
- Owners: Security + ML + Privacy, UNASSIGNED
- Gates: S1-READY, DRG-01
- Plan refs: §37–§41

## Decision

- Todo OCR/IA externo pasa por AI Gateway.
- Egress minimizado, redacción fail-closed, política por company y auditoría.
- IA propone clasificación, mapping o narrativa grounded.
- IA no calcula dinero, confirma matches, autoriza acceso, cierra periodos ni decide retención.
- Fallback determinístico y abstención son obligatorios.
- Needle queda fuera del camino crítico.

## Consequences

Control central de proveedores/costo/riesgo; añade gateway, evals y latencia.

## Verification

Antes de IA real: dataset de eval, prompt injection, redactor, shadow/canary/rollback y presupuesto.


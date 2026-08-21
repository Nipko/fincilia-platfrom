# ADR-015 — Deduplicación cross-source segura

- Status: Accepted
- Date: 2026-08-21
- Owners: Data + Accounting, UNASSIGNED
- Gate: S1-READY
- Task: FNC-DOM-004
- Plan refs: §17

## Decision

- Source record es evidencia.
- Money movement es evento económico.
- Movement evidence link relaciona N evidencias.
- Dedupe candidate es sospecha.
- Merge decision conserva justificación.

Claves duras solo usan hash/ID estable del proveedor/versiones definidas. Company, cuenta, fecha, monto, dirección y referencia generan candidato, nunca UNIQUE.

## Consequences

Evita borrar pagos legítimos idénticos; requiere decisiones de merge y revisión.

## Verification

TST-IDEM-001 y TST-DED-001.


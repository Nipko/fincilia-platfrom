# ADR-005 — Linaje por campo

- Status: Accepted
- Date: 2026-08-21
- Owners: Data + Accounting, accountable FOUNDER-01
- Gate: S1-READY
- Tasks: FNC-DOM-005
- Plan refs: §18

## Decision

Origin locator identifica artefacto/version, página/hoja, fila/columna/celda o bounding box, parser/modelo, receta/overlay y campo.

Lineage edge enlaza cada transformación hasta campo canónico, match, informe y cierre. El localizador no se muta; una corrección crea overlay o versión.

## Consequences

Mayor almacenamiento y complejidad, pero evidencia reproducible y explicación verificable.

## Verification

TST-LIN-001 exige camino completo para 100% de campos publicados y decisiones financieras.

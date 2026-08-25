# ADR-006 — Recetas determinísticas y overlays

- Status: Accepted
- Date: 2026-08-21
- Owners: Data + Product, accountable FOUNDER-01
- Gate: S1-READY
- Plan refs: §8, §18

## Decision

- Limpieza usa DSL determinística, versionada y reproducible.
- Cada paso tiene preview, diff, validación y undo.
- Corrección manual es overlay con actor/motivo; nunca altera raw.
- Template incluye fingerprint de fuente/esquema.
- Schema drift bloquea aplicación silenciosa y crea nueva versión.

## Consequences

Facilita auditoría y reutilización; requiere diseño de DSL, versionado y compatibilidad.

## Verification

Reejecución sobre mismo input/release produce mismo resultado; drift cambia estado a revisión.

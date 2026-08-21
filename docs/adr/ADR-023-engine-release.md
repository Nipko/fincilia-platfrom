# ADR-023 — Engine release y reproducibilidad

- Status: Accepted
- Date: 2026-08-21
- Owners: Architecture + Data + Security, UNASSIGNED
- Gate: S1-READY
- Task: FNC-DOM-005
- Plan refs: §18

## Decision

Cada resultado fija engine_release con:

- semver.
- commit.
- SHA-256 del artefacto.
- SBOM.
- canonical schema version.
- clasificación neutral o affects_results.

Una release affects_results se ejecuta sobre corpus adjudicado antes del deploy. Cierres/snapshots conservan release y todas las versiones de reglas/datos.

## Consequences

Permite reproducir resultados históricos y explicar cambios; aumenta disciplina de build, artefactos y pruebas.

## Verification

TST-PAR-001 reproduce un dataset desde input/versiones; un cambio affects_results produce nueva versión, nunca reescritura.


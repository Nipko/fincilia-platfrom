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

El perfil de implementación, todavía pendiente de ratificación de Platform y Security,
completa esos mínimos con: `engine_release_id`, estado y aprobación; árbol fuente limpio;
digests de artefactos y lockfile; formato/versión/digest de SBOM; provenance, attestation y
firma; identidad y timestamp del builder; componentes incluidos; compatibilidad de esquema;
y referencias al corpus y reporte de evaluación. La lista ejecutable autoritativa vive en
`lineage-model.json#engine_release_contract.required_fields`; ninguna versión flotante la
puede sustituir.

Los nombres interoperables del perfil ampliado incluyen `source_tree_clean`,
`dependency_lock_digest`, `build_provenance_ref`, `attestation_ref`, `signature_ref`,
`builder_identity` y `build_timestamp`.

Una release affects_results se ejecuta sobre corpus adjudicado antes del deploy. Cierres/snapshots conservan release y todas las versiones de reglas/datos.

## Consequences

Permite reproducir resultados históricos y explicar cambios; aumenta disciplina de build, artefactos y pruebas.

## Verification

TST-PAR-001..007 cubren determinismo, evaluación de `affects_results`, equivalencia de
`neutral`, build limpio/SBOM, no sobrescritura, preservación de snapshots y revocación.

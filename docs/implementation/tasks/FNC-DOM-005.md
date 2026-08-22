---
task: FNC-DOM-005
title: Linaje por campo, overlays y engine release reproducible
status: review_pending
implementer: Claude (external agent) + Integration Steward
base_sha: a43bc1c
base_sha_verified: true
integration_base_sha: 5fb0220
gate: S1-READY
data_ceiling: synthetic_only
independent_reviewers: [Data, Accounting, Architecture, Security, Privacy]
---

# Resultado esperado

Convertir ADR-005, ADR-006 y ADR-023 en un contrato ejecutable que garantice linaje
completo por campo/decisión, overlays append-only y reproducción fijada por release y
manifest; ningún resultado usa `latest` ni reescribe históricos.

## Rutas entregadas

- `docs/domain/LINEAGE_SPEC.md`
- `docs/domain/lineage-model.json`
- `tools/lineage_model/**`
- `docs/implementation/handoffs/FNC-DOM-005.md`
- `docs/implementation/evidence/FNC-DOM-005/README.md`
- Integración en CI, estado de fase, trazabilidad y catálogo de pruebas.

Claude no modificó los archivos centrales. El Integration Steward realizó su integración
después del handoff.

## Dependencias

- FNC-DOM-002, FNC-DOM-003, FNC-DOM-004.
- FNC-ARC-002, FNC-SEC-002 y FNC-PRV-001.
- ADR-004, ADR-005, ADR-006 y ADR-023.
- DR-PRV-001 permanece Proposed; el contrato propaga tags, no inventa taxonomía legal.

## Criterios de aceptación

1. Origin locators tipados e inmutables cubren tabla, PDF/imagen, XML y API/records.
2. Todo campo publicado/decisión tiene path completo hasta evidencia versionada.
3. Grafo acíclico, company-scoped, append-only y sin valores raw en aristas/logs.
4. Overlay stale/conflictivo falla; undo es otro overlay y no muta raw/histórico.
5. Campos financieros críticos exigen SoD antes de uso autoritativo.
6. Engine release fija commit, artefactos, SBOM, provenance, esquema y evaluación.
7. Reproduction manifest no usa `latest`; mismo manifest produce mismo digest o falla.
8. Reprocess crea versión/diff/impact y conserva snapshots históricos.
9. Privacidad/retención/tombstones se propagan sin aceptar decisiones Legal pendientes.
10. Validador determinista y tests negativos pasan solo con datos sintéticos.

## Fuera de alcance

- Migraciones, SQL, object store, parser/OCR, UI o código productivo.
- IA/proveedores externos o datos reales.
- Aprobar releases, retención, región, clasificación legal o gates.

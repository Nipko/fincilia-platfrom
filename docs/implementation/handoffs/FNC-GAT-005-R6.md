---
task_id: FNC-GAT-005
status: IN_PROGRESS
base_sha: 29f86e82f22fd671aeff894a8527a881da8e6f3a
release_candidate_run: 33828310759
data_ceiling: synthetic_only
gate_effect: evidence_only
independent_reviewers: [Security, QA]
---

# Handoff FNC-GAT-005 R6 — evidencia supply chain vigente

El control `G00-SUPPLY-CHAIN` quedó actualizado al candidato firmado
`33828310759`. Su inventario usa los ocho materiales cerrados de FNC-SUP-004 y
queda ligado al commit completo `29f86e82f22fd671aeff894a8527a881da8e6f3a`.

El archivo de 223985 bytes tiene SHA-256
`219070cd9debfc0ac94bc5ffca80179fd3eb3294bf5a612b8a8a4b33508452ff`.
Bundle, fuente y archivo fueron verificados localmente; procedencia SLSA y SBOM
SPDX fueron verificados nuevamente con `gh attestation verify` y selectores
exactos de repositorio, workflow, commit y rama.

Esto reemplaza una evidencia técnicamente incompleta, pero conserva
`independent_review.state = pending`, `real_data_authorized = false` y
`production_authorized = false`. DRG-00/DRG-01 no cambian de estado.

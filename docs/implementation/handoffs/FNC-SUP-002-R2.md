---
task_id: FNC-SUP-002
status: REVIEW_PENDING
base_sha: f05fdbd6cc6e207cfeff3bc028bdd1a15b704256
tested_head_sha: f05fdbd6cc6e207cfeff3bc028bdd1a15b704256
data_ceiling: synthetic_only
gate_effect: evidence_only
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Security, QA]
---

# Handoff FNC-SUP-002 R2 — candidato vigente firmado

## Resultado

El workflow manual `release-candidate.yml` construyó y probó las imágenes API,
worker y web del commit exacto `f05fdbd6cc6e207cfeff3bc028bdd1a15b704256`
sin publicarlas. Produjo dos veces el bundle determinista, archivó el candidato y
emitió attestations de procedencia SLSA y SBOM SPDX con la identidad OIDC del
workflow.

## Evidencia externa

| Campo | Valor |
|---|---|
| Run | `33349841370`, `success` |
| URL | `https://github.com/Nipko/fincilia-platfrom/actions/runs/33349841370` |
| Fuente | `f05fdbd6cc6e207cfeff3bc028bdd1a15b704256`, `refs/heads/main` |
| Esquema | `V0045` |
| Sujeto | `fincilia-release.tar.gz` |
| SHA-256 | `963dd6231381ead4369c14d3ad9eedf5014a12518f11ca2d9ebd4618e7c93e71` |
| Procedencia | `https://slsa.dev/provenance/v1`, verificada |
| SBOM | `https://spdx.dev/Document/v2.3`, verificado |
| Signer | `github.com/Nipko/fincilia-platfrom/.github/workflows/release-candidate.yml` |
| Runner | GitHub-hosted; self-hosted denegado durante verificación |

La evidencia estructurada está en
`docs/implementation/evidence/FNC-SUP-002-R2.json`. El bundle descargado se
verificó fuera del runner con `verify`, `verify-source`, `verify-archive` y dos
invocaciones de `gh attestation verify` ligadas a repositorio, workflow, commit,
ref y tipo de predicado.

## Verificación

- Workflow: 1 job, 16 pasos, `success` en 1m29s.
- `tools.release_candidate.test_release_candidate`: 27 OK.
- `tools.supply_chain.test_validate`: 80 OK.
- `tools.quality_gate.test_repo_policy`: 10 OK.
- `tools.supply_chain.cli validate`: modelo válido; exit 1 esperado por un
  bloqueo high de origen independiente y seis monitores OCI medium.

## Límites y pendientes

- No se publicaron imágenes ni se desplegó AWS.
- Sólo se usaron datos sintéticos; datos reales y producción siguen denegados.
- `EVC-SOURCE-VERIFIED`, TM-005 y DRG-00 continúan abiertos.
- Security y QA deben hacer revisión independiente; esta ejecución del agente
  no cuenta como esa aprobación.

## Rollback

Revertir únicamente el commit de actualización R2 y descartar el artefacto del
run `33349841370`. No hay migraciones, datos ni runtime persistente que revertir.

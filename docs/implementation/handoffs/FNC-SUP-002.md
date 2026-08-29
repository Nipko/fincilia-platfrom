---
task_id: FNC-SUP-002
status: REVIEW_PENDING
base_sha: 0c148e66d0ad27860ab23d752f3a5a40ce63ecaf
reservation_sha: 6714740
implementation_shas: [daabb01, 1aa44c2, ffa6099]
tested_head_sha: ffa6099475c1fd7d063c1752904ec879ba7be2e7
data_ceiling: synthetic_only
gate_effect: evidence_only
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Security, QA]
---

# Handoff FNC-SUP-002 — candidato firmado y verificable

## Resultado

El candidato se empaqueta como `tar.gz` determinista con inventario exacto,
metadatos normalizados y rechazo de links, traversal, extras y tamper. El bundle
1.1 añade un SPDX 2.3 agregado que cubre los inventarios de API, worker y web.

El workflow manual usa `actions/attest` fijada al SHA oficial de v4.1.1. Emite
procedencia SLSA y SBOM firmados por la identidad OIDC del workflow. La policy
del repo permite solamente `id-token: write` y `attestations: write` en ese
archivo manual; permisos adicionales, nivel job, push/PR u otro workflow fallan.

## Evidencia externa y segunda verificación

| Campo | Valor |
|---|---|
| Run | `33256843904`, success |
| Fuente | `1aa44c29af51709e7f675cdeee76c453fc30f416`, `refs/heads/main` |
| Sujeto | `fincilia-release.tar.gz` |
| SHA-256 | `81b87a7d161f002bc74acf08c3b26ab2009bfcaa8870d5a7f5c538817560d32e` |
| Procedencia | `https://slsa.dev/provenance/v1`, verificada |
| SBOM | `https://spdx.dev/Document/v2.3`, verificado |
| Signer | `github.com/Nipko/fincilia-platfrom/.github/workflows/release-candidate.yml` |
| Runner | self-hosted denegado durante verificación |

Evidencia resumida: `docs/implementation/evidence/FNC-SUP-002.json` con digest
`ed6b6838ad41dd25daf5647fcd10ae4128d389f1edd05991baed8953ac4b67d7`.
El bundle descargado verificó con `verify`, `verify-source`, `verify-archive` y
dos invocaciones offline de `gh attestation verify`.

## Pruebas

- `tools.release_candidate.test_release_candidate`: 27 OK.
- `tools.supply_chain.test_validate`: 80 OK.
- `tools.quality_gate.test_repo_policy`: 10 OK.
- Quality gate sobre cada índice: 0 findings.
- Supply-chain: bloqueos high 4 → 1.

## Defectos encontrados por ejecución

1. El fixture Windows convertía CRLF dos veces y producía una falsa modificación
   Git; se fijó LF explícito.
2. El quality gate rechazó correctamente OIDC write. La excepción inicial no se
   silenció: se convirtió en una allowlist exacta con tres pruebas negativas.
3. Subir los bundles Sigstore con su nombre temporal podía colisionar; se copian
   a nombres únicos antes de preservar el artefacto.

## Bloqueos y límites

- `EVC-SOURCE-VERIFIED` sigue pendiente de Security independiente. Los cinco tags
  oficiales se observaron por API y coinciden, pero la observación del agente no
  es aceptación.
- Seis scopes OCI carecen de monitor compatible; son medium y no se ocultan.
- TM-005, DRG-00 y DRG-01 permanecen abiertos.
- Las imágenes no se publicaron. La firma cubre el archivo candidato, no un
  digest de registry ni cada dependencia upstream.
- No se usaron datos reales ni se habilitó producción.

## Rollback

Revertir `daabb01` y `1aa44c2` retira archivo, attestations y excepción estrecha
de permisos. Descartar el artefacto externo no requiere migración ni purga.

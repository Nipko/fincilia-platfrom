---
task: FNC-GAT-005
status: REVIEW_PENDING
base_sha: 1d6910d4da386821543079466288bb4c2dadc91b
release_candidate_run: 33799835562
data_ceiling: synthetic_only
gate_effect: evidence_only
---

# Handoff FNC-GAT-005 R4 — renovación de evidencia para V0057

## Resultado

La publicación del centro legal en inglés añadió V0057 y cambió API/web, por
lo que la evidencia de V0056 dejó de cubrir el árbol actual. No se relajó el
validador. Se generó un candidato desde el `main` exacto
`1d6910d4da386821543079466288bb4c2dadc91b`.

El run manual `33799835562` terminó en verde. Construyó y ejercitó API, web y
worker, reprodujo el bundle, generó el SBOM SPDX, firmó procedencia y SBOM con
OIDC y verificó ambas firmas. El archivo descargado se comprobó fuera del
runner contra el repositorio, el workflow, la rama y el SHA exactos.

## Evidencia

- Sujeto `fincilia-release.tar.gz`: 224177 bytes, SHA-256
  `afd4477d97ec9bd57496b978603541c97365662003c629996b8c2ca6dbf275b5`.
- Esquema: `V0057`; contrato de bundle: `1.1.0`.
- Sigstore procedencia:
  `bfb3d4adf8e10c4ac3524ba16ccd95e7a5f095300f260a3fe6cccb66820be7c5`.
- Sigstore SBOM:
  `14a248a9f94e43e1cc0bafafa9d0454cdd5ea1c665871b4fc4db573811d46c30`.
- Los doce inputs proceden del manifiesto firmado y se vuelven a calcular
  contra los blobs Git actuales.
- Las dos attestations fueron verificadas fuera del runner con
  `gh attestation verify` y resultaron válidas.

## Límites y revisión

La evidencia no autoriza producción ni datos financieros reales y no
constituye revisión humana. Security y QA continúan como revisores
independientes pendientes. El Founder no cuenta como revisor independiente y
los blockers de DRG-00/DRG-01 permanecen visibles.

## Rollback

Si la proyección fuera inválida, devolver `G00-SUPPLY-CHAIN` a `pending` y
retirar esta evidencia en un commit nuevo. No restaurar evidencia de V0056 como
si cubriera V0057.

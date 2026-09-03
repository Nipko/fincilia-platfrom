---
task: FNC-GAT-005
status: REVIEW_PENDING
base_sha: b1bcbe0533fd8b42aa12aea3ac0da3b67bf16bb8
release_candidate_run: 33794308981
data_ceiling: synthetic_only
gate_effect: evidence_only
---

# Handoff FNC-GAT-005 R3 — renovación de evidencia para V0056

## Resultado

El primer CI de FNC-LEG-002 (`33793869545`) detectó correctamente que añadir
V0056 y cambiar API/web hizo obsoleta la evidencia de cadena de suministro. No
se relajó el validador ni se ocultó el drift. Se generó un candidato nuevo desde
el `main` exacto `b1bcbe0533fd8b42aa12aea3ac0da3b67bf16bb8`.

El run manual `33794308981` terminó en verde: construyó API, web y worker,
ejercitó las imágenes, reprodujo dos veces el bundle, generó SPDX, firmó
procedencia y SBOM mediante OIDC y verificó ambas firmas. El archivo descargado
se volvió a comprobar fuera del runner contra repositorio, workflow, rama y SHA
exactos.

## Evidencia

- Sujeto `fincilia-release.tar.gz`: 224181 bytes, SHA-256
  `b009d242dbefb81613835f8a2d6b146ef4976c546fd7d0c917c03c04be39680c`.
- Esquema: `V0056`; contrato de bundle: `1.1.0`.
- Sigstore procedencia:
  `b40f7a57dcbd5375ee698b42974e5ce5da23f715adbc8501b9327225f4eef972`.
- Sigstore SBOM:
  `d58460cee99926e5eb28b90cb428e1bf8ccd469560b14364ed83cc319f82c625`.
- Los doce inputs se copiaron del manifiesto firmado y el validador vuelve a
  calcularlos desde los blobs Git actuales.
- `python3 -m unittest tools.drg01_readiness.test_validate -v`: 18, OK.
- `python3 -m tools.drg01_readiness.validate`: `ok: true`, 13 blockers,
  DRG-00/01 `not_met`, `real_data_authorized: false`.

La primera verificación local de fuente falló porque el propio artefacto
descargado estaba dentro del worktree. Se movió al directorio temporal, el
árbol quedó limpio y `verify-source` pasó sobre el mismo bundle. El artefacto
temporal no se incorpora a Git.

## Límites y revisión

La evidencia no publica imágenes, no despliega, no autoriza producción ni
datos reales y no constituye revisión humana. Security y QA continúan como
revisores independientes pendientes. El Founder no cuenta como revisor
independiente y los 13 blockers declarados permanecen visibles.

## Rollback

Si esta proyección fuera inválida, devolver `G00-SUPPLY-CHAIN` a `pending` y
retirar la evidencia R3 en un commit nuevo. Nunca restaurar la evidencia V0055
como si cubriera V0056.

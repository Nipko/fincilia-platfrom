---
task_id: FNC-SUP-004
status: REVIEW_PENDING
base_sha: 7772605688e7226720f499559a3953c4c4612d7b
implementation_sha: 29f86e82f22fd671aeff894a8527a881da8e6f3a
release_candidate_run: 33828310759
data_ceiling: synthetic_only
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Security, QA, Platform/SRE]
---

# Handoff FNC-SUP-004 — cobertura cerrada de fuentes Docker

## Resultado

El contrato ya no enumera una selección manual de archivos. Ocho materiales
disjuntos cubren los tres Dockerfiles, dependencias, configuración de build,
tests, archivos públicos, migraciones, bootstrap, herramienta de release y el
workflow firmante que las imágenes incorporan.

El validador extrae dinámicamente cada origen local de `COPY`; distingue
copias entre etapas y falla cerrado ante `ADD`, rutas dinámicas, traversal,
inputs solapados, JSON inválido, heredoc o flags ambiguos. Por tanto un nuevo
`COPY` fuera del inventario no puede producir un candidato aparentemente
completo.

## Evidencia

- 32 pruebas unitarias del candidato, incluidas mutaciones adversariales, OK.
- 24 pruebas integradas de readiness y evidencia técnica, OK; work graph y
  catálogo válidos sin hallazgos bloqueantes.
- Quality gate sobre el índice Git, OK.
- Work graph: 143 tareas, 382 aristas, válido.
- Candidato `33828310759` sobre
  `29f86e82f22fd671aeff894a8527a881da8e6f3a`: 17 pasos verdes en 5m33s.
- Bundle, checkout exacto y archivo verificados fuera del runner.
- Attestations SLSA y SPDX revalidadas fuera del runner contra repositorio,
  workflow, commit, rama y prohibición de runner self-hosted.

## Bloqueos preservados

La ejecución sólo usó datos sintéticos. No aprueba la release, no despliega
AWS, no autoriza producción ni datos reales y no satisface la revisión humana
independiente de Security/QA/Platform.

## Rollback

Revertir `38dfb9e` elimina el extractor; revertir `29f86e8` elimina su enlace
al workflow y la optimización de verificación. Cualquiera invalida expresamente
la evidencia nueva. No existe estado de datos o infraestructura que revertir.

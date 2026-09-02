---
task: FNC-GAT-005
status: REVIEW_PENDING
base_sha: 74d554dc6fb085817be091b5f621b46e1e07d72a
implementation_sha: 80afea520ced03ab1a2f153e4939c87113bbfd2a
tested_sha: 80afea520ced03ab1a2f153e4939c87113bbfd2a
data_ceiling: synthetic_only
gate_effect: evidence_only
---

# Handoff FNC-GAT-005 R2 — cadena de suministro DRG-00

## Resultado

`G00-SUPPLY-CHAIN` pasa con un candidato completamente sintético, determinista
y ligado a los inputs actuales. El archivo de release y su SBOM SPDX tienen
attestations Sigstore emitidas por OIDC con procedencia SLSA; ambas firmas se
verificaron dentro del runner y otra vez fuera de él contra repositorio, workflow,
commit y rama exactos.

DRG-00 y DRG-01 permanecen `not_met`. El informe deriva 13 blockers y
`real_data_authorized=false`; este cambio no admite una release para documentos
reales, no publica imágenes y no registra una revisión humana.

## Evidencia

- Release candidate: run `33694283964`, success sobre
  `74d554dc6fb085817be091b5f621b46e1e07d72a`.
- CI de integración: run `33696296558`, success sobre
  `80afea520ced03ab1a2f153e4939c87113bbfd2a`.
- Evidencia durable:
  `docs/implementation/evidence/FNC-GAT-005-SUPPLY-CHAIN.json`.
- Sujeto: `fincilia-release.tar.gz`, SHA-256
  `7a137dfff6da95c30c256d5b3a62b21bf33f04355b6b318f82a8bfe7be32b54e`,
  esquema `V0055`.
- El validador recalcula los 12 inputs desde blobs Git. Un cambio de API, web,
  worker, contratos, plataforma o migraciones vuelve obsoleta la evidencia.

## Verificación

- `python3 -m unittest tools.drg01_readiness.test_validate`: 16 tests, OK.
- `python3 -m tools.drg01_readiness.validate`: modelo válido, 13 blockers,
  DRG-00/01 `not_met`, datos reales no autorizados.
- `python3 -m tools.work_graph.validate`: 134 tareas, 353 dependencias, OK.
- `python3 -m tools.quality_gate.cli` sobre el índice: 0 hallazgos.
- CI ejecutó además repositorio/política sintética, PostgreSQL, migraciones,
  API, worker, Chromium y Axe; todos los carriles aplicables pasaron.

La repetición local conjunta de release y supply-chain se interrumpió después de
10 minutos por E/S no responsiva de Git sobre el montaje Windows/WSL. La misma
batería concluyó después en el runner Linux nativo del CI y quedó verde.

## Rutas integradas

- `tools/drg01_readiness/model.py` y `test_validate.py`.
- `docs/security/drg01-readiness.json` y `DRG01_READINESS.md`.
- evidencia, solicitud de decisión, trazabilidad, backlog y fase vigente.

## Pendientes y revisiones

DRG-00 conserva cinco blockers: `G00-ISOLATED-ENV` y cuatro controles humanos
(`G00-LEGAL`, `G00-RETENTION`, `G00-REGION`,
`G00-INDEPENDENT-REVIEW`). Security y QA deben revisar de forma independiente
la identidad firmante y el alcance; su revisión sigue `pending` y no fue
inferida de la ejecución automática.

## Rollback

Revertir `80afea5`, devolver `G00-SUPPLY-CHAIN` a `pending` y retirar la
evidencia durable. Nunca cambiar solo el estado del control: el validador debe
seguir fallando cerrado si falta la evidencia o si los inputs actuales difieren.

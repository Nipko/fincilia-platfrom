---
task: FNC-GAT-005
status: IN_PROGRESS
base_sha: 89145a75a1e16dc476e42f78af370f826aff037f
tested_sha: 89145a75a1e16dc476e42f78af370f826aff037f
data_ceiling: synthetic_only
gate_effect: evidence_only
---

# Handoff FNC-GAT-005 R7 — renovación de cadena de suministro

## Resultado

La evidencia durable de `G00-SUPPLY-CHAIN` vuelve a corresponder exactamente al
código ejecutable vigente. El candidato se construyó sobre el SHA de `main`, fue
firmado con la identidad OIDC del workflow autorizado y se verificó tanto dentro
del runner como fuera de él. No se publicaron las imágenes de este candidato ni
se autorizó producción o información real.

DRG-00 y DRG-01 permanecen `not_met`: el modelo válido deriva 13 blockers y
`real_data_authorized=false`. Las revisiones humanas Security/QA continúan
pendientes y no se atribuyen al autor de este cambio.

## Evidencia reproducible

- Workflow manual `fincilia-release-candidate`: run `33917287024`, exitoso en
  `89145a75a1e16dc476e42f78af370f826aff037f`.
- Bundle determinista y archivo verificados contra el checkout limpio fuera del
  runner; esquema observado `V0057`.
- SLSA provenance y SBOM SPDX verificadas de nuevo contra repositorio, workflow,
  rama y source digest exactos, rechazando runners autohospedados.
- Proyección durable:
  `docs/implementation/evidence/FNC-GAT-005-SUPPLY-CHAIN.json`.
- `python3 -m unittest tools.drg01_readiness.test_validate -v`: 19 pruebas, OK.
- `python3 -m tools.drg01_readiness.validate`: modelo válido, 13 blockers,
  hallazgos vacíos y datos reales no autorizados.

## Motivo de la renovación

El bootstrap PostgreSQL cambió dentro de `db`, que forma parte explícita de los
inputs del candidato. El validador detectó correctamente el drift y CI falló
cerrado; la evidencia se renovó mediante una corrida firmada real, no copiando
digests ni rebajando la política.

## Pendientes

`G00-ISOLATED-ENV`, la identidad administrada, restore, PCI, pentest, DPA y las
revisiones independientes siguen abiertos. Este handoff no modifica esos estados
ni sustituye la adjudicación humana.

## Rollback

Revertir conjuntamente este handoff, la fila de fase y la proyección durable.
Nunca conservar una proyección cuyo inventario no coincida con los inputs
actuales: el validador debe volver a bloquearla.

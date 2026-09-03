---
id: FNC-GAT-007-R2
status: REVIEW_PENDING
base_sha: d466438a8f1fd9ed8f37dee0ca5467caca697d94
integration_sha: pending_this_handoff
data_ceiling: synthetic_only_until_gate
author: Codex principal dev + Integration Steward
independent_reviewers: [Security, Platform/SRE, QA]
---

# Handoff FNC-GAT-007 R2 — plan cold y evidencia CI

## Resultado

El preflight quedó ligado a dos observaciones redactadas y reproducibles. La
primera confirma que `private-pilot` está ausente en la cuenta objetivo. La
segunda registra el plan OpenTofu `cold` actual sin conservar el plan binario,
estado, outputs, endpoints, secretos ni el identificador de cuenta en claro.

El plan observado sobre `d466438a8f1fd9ed8f37dee0ca5467caca697d94`
contiene 142 altas, 11 lecturas, cero actualizaciones y cero borrados. Su digest
es `c99de724cfed0d804129d1ef62634c23054c4893bdc29cd265d1a8a938aaa914`.
No se ejecutó `apply` y esta evidencia no constituye autorización para hacerlo.

## Evidencia

- Preflight live:
  `docs/implementation/evidence/FNC-GAT-007-PREFLIGHT.json`, digest canónico
  `e2d892fbe200176786f07dae757c1e25ba521c7ef2e04097392c16bd1f46110c`.
- Plan cold:
  `docs/implementation/evidence/FNC-GAT-007-COLD-PLAN.json`, digest canónico
  `c356583235eb50fe0f8b2cdc7a3aaf76074b8ca1dacc7052e95123952f1850cb`.
- CI del primer incremento: run `33703667116`, `success`.
- CI del segundo incremento: run `33704530655`, pendiente al escribir este
  incremento; su resultado se añadirá en una corrección R3 si fuera necesario.
- Suite focal `tools.aws_pilot_control.test_control`: 20 pruebas, OK.

## Límites y bloqueos

La autorización histórica de un plan de 27 recursos no cubre este plan de 142
altas. Antes de cualquier `apply` hacen falta revisión de coste para `sa-east-1`,
autorización nominal ligada al digest vigente y nueva planificación si cambia el
código o el inventario remoto.

El control `G00-ISOLATED-ENV` sigue `pending`. También permanecen pendientes la
admisión del release, el drill sintético completo en el target y la revisión
independiente de Security, Platform/SRE y QA. `DRG-00` y `DRG-01` siguen
`not_met`; `real_data_authorized=false`.

## Operaciones realizadas

Las llamadas AWS fueron de solo lectura y la planificación fue local. No se
creó, modificó ni eliminó ningún recurso cloud; no se publicaron imágenes, no se
leyeron secretos y no se ingresaron datos financieros ni personales reales.

## Rollback

Eliminar únicamente la evidencia del plan y su prueba devuelve el repositorio al
preflight anterior. No existe rollback cloud porque no hubo `apply` ni mutación.

---
id: FNC-GAT-007
status: REVIEW_PENDING
base_sha: aadef53f37c4043190a1fff6b7375d690212b30e
code_sha: 0c0abe7948ca661a314a94e35be95bd3690da1c0
integration_sha: pending_this_handoff
data_ceiling: synthetic_only_until_gate
author: Codex principal dev + Integration Steward
independent_reviewers: [Security, Platform/SRE, QA]
---

# Handoff FNC-GAT-007 — preflight del entorno aislado

## Resultado

El control `G00-ISOLATED-ENV` ya tiene una frontera técnica comprobable. El
controlador valida la cuenta y región, consulta RDS/ECS/NAT/ALB/Valkey y obtiene
únicamente direcciones mediante `tofu state list`. No lee estado completo,
outputs, endpoints, secretos ni variables de entorno arbitrarias.

La consulta live del `2026-09-03T01:35:59Z` confirmó que la cuenta exacta no
tiene aplicado el entorno separado `private-pilot`: foundation `0/33`, runtime
`0/10`, RDS/Valkey/ALB/ECS ausentes y cero NAT. La evidencia guarda un digest
de la cuenta, nunca el identificador en claro, y declara que no hubo mutación.

## Hueco corregido

FNC-QA-001 contiene un drill sintético local válido, pero el agregador permitía
que ese mismo fichero respaldara `G00-ISOLATED-ENV`. Ahora los tres controles
compartidos `INVENTORY/DELETE/DRILL` conservan esa evidencia y el entorno
aislado exige otro artefacto: `FNC-GAT-007.json`, ligado a los 43 recursos
mínimos, release admitida, Cognito/Google y un drill target distinto. El
validador también exige que la referencia de ese drill sea exactamente
`FNC-GAT-007-TARGET-DRILL.json` y exista.

## Evidencia

- `docs/implementation/evidence/FNC-GAT-007-PREFLIGHT.json`, digest canónico
  `e2d892fbe200176786f07dae757c1e25ba521c7ef2e04097392c16bd1f46110c`.
- 81 pruebas de controlador, contrato private-pilot y publicación: OK.
- 36 pruebas focales de controlador/readiness después del cierre: OK.
- `tools.work_graph.validate`: 136 tareas, 358 aristas, cero errores.
- `tools.drg01_readiness.validate`: modelo válido, 13 blockers, ambos gates
  `not_met`, `real_data_authorized=false`.
- Quality gate sobre el índice del primer incremento: OK.
- CI del primer incremento: pendiente de sellado en R2.

## Estado y siguiente operación

La tarea está lista para revisión; el gate no. Para construir el entorno faltan
un plan actualizado y una autorización expresa sobre ese plan, porque su apply
creará recursos persistentes y facturables. Después se publican imágenes por
digest, se calienta con ECS en cero, se configura identidad/secretos fuera de
IaC y se ejecuta el drill completamente sintético en el target. Solo esa futura
evidencia puede cambiar el control automático; Security/Platform/SRE/QA siguen
siendo revisores humanos independientes.

No se creó, modificó ni eliminó ningún recurso AWS. No se aceptó ADR-032 ni
DRG-00/01 y no se autorizó información financiera real.

## Rollback

Revertir el commit del controlador y retirar las dos constantes de evidencia
restaura el comportamiento anterior. No existe rollback cloud porque todas las
operaciones fueron de solo lectura.

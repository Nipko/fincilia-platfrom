---
id: FNC-GAT-006-R5
corrects: FNC-GAT-006
status: REVIEW_PENDING
base_sha: 5d44656
integration_sha: pending_this_handoff
data_ceiling: synthetic_only_until_DRG-01
author: Codex principal dev + Integration Steward
independent_reviewers: [Security, Privacy, Database, Data, QA]
---

# Handoff FNC-GAT-006 R5 — evidencia religada al listener HTTPS

## Defecto y corrección

El primer `warm` real demostró que ECS intentaba asociar el target group antes
de existir el listener HTTPS, porque ACM aún no había sido validado. El servicio
de aplicación ahora depende explícitamente del listener y sólo existe cuando
`certificate_ready=true`. El worker y los jobs one-off conservan capacidad cero
y permiten bootstrap sin publicar tráfico ni abrir un listener HTTP temporal.

La modificación de `compute.tf` hizo fallar cerrada la evidencia adjudicada de
DRG-01. Se recalcularon únicamente el digest de esa fuente y el digest canónico:

- `compute.tf`: `2d28a0a56e75b3cbff634e1234df45712dc6d9b0386a3c624afabee64cf0f6a4`;
- evidencia: `d6a3eea5e741a4e1505f3b088f1510a59777c2d6aa2243b560dbe03675889b6b`.

## Límites

No cambiaron los 90 casos adjudicados, selectores, controles técnicos,
limitaciones ni fecha observada. El ajuste no valida ACM, no habilita tráfico,
no acepta revisión independiente y no autoriza datos reales. DRG-00/01
permanecen `not_met`.

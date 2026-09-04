---
id: FNC-GAT-006-R6
corrects: FNC-GAT-006
status: REVIEW_PENDING
base_sha: 0eda8ad
integration_sha: pending_this_handoff
data_ceiling: synthetic_only_until_DRG-01
author: Codex principal dev + Integration Steward
independent_reviewers: [Security, Privacy, Database, Data, QA]
---

# Handoff FNC-GAT-006 R6 — evidencia religada al bootstrap RDS

## Defecto y corrección

La ejecución real confirmó que el secreto maestro administrado por RDS expone
`username` y `password`, pero no `host` ni `port`. El job de bootstrap ahora
toma esos dos selectores no secretos del recurso RDS y mantiene exclusivamente
las credenciales en Secrets Manager. No cambia su red privada, usuario de
contenedor, orden de ejecución ni techo de datos.

La modificación hizo fallar cerrada la evidencia adjudicada. Se recalcularon
únicamente el digest de `compute.tf` y el digest canónico:

- `compute.tf`: `9952113a7ef4a2846e4a7999e6c65846a00fb3e1cb9b86c08cfd1b434cf2b7ce`;
- evidencia: `eff5578503564eefc33c0c047f8cf4fa0225bb938d9b9b7bb596167bdc17bb56`.

## Límites

Los 90 casos adjudicados y sus resultados permanecen idénticos. Este ajuste no
acepta revisiones, no habilita servicios o tráfico y no autoriza datos reales.
DRG-00/01 permanecen `not_met`.

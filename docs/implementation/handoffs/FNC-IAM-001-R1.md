---
task: FNC-IAM-001
status: REVIEW_PENDING
supersedes_handoff_only: docs/implementation/handoffs/FNC-IAM-001.md
correction_task: FNC-IAM-003
implementation_shas: [e0f8154, 3fc4341, c0d9ef0]
data_ceiling: synthetic_only_until_DRG-00
---

# Correccion de assurance y cierre de sesion

El handoff original pedia demostrar MFA de Cognito para el acceso Google. Esa
garantia era demasiado amplia: Cognito delega los factores primario y MFA al
IdP federado, y `openid email profile` no prueba a Fincilia que Google haya
usado segundo factor.

FNC-IAM-003 corrige el contrato: MFA `ON` se conserva para identidades nativas,
`SignUp` nativo queda cerrado y Google se declara assurance federado sin afirmar
MFA. La solicitud `UD-IAM-FEDERATED-MFA` recomienda conservar Google para la beta
con invitacion nominal, sesion corta y 2SV como regla operativa no verificable.

Ademas, salir elimina sesion/nombre/transaccion OAuth y termina la sesion Hosted
UI mediante un `logout_uri` exacto y same-origin. La sonda live de 16 controles
queda preparada para el despliegue, pero no se ha ejecutado porque el plano AWS
objetivo aun no esta aplicado.

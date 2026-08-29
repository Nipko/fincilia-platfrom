---
task_id: FNC-IAM-003
status: REVIEW_PENDING
base_sha: 46d57a3025d7402c7a90b4cb7e8002c50bc02a68
implementation_shas: [e0f8154, 3fc4341, c0d9ef0]
tested_head_sha: c0d9ef0
data_ceiling: synthetic_only_until_gate
gate_effect: none
independent_reviewers: [Security, Privacy/Legal, Architecture, QA]
---

# Handoff FNC-IAM-003 — cierre operativo de identidad

## Resultado

- POST same-origin `/api/auth/oidc/logout` construye server-side el endpoint
  Cognito, elimina las tres cookies y vuelve exactamente a `/entrar`.
- Configuracion incompleta borra la sesion local y falla de forma estable; un
  origen externo no puede provocar logout CSRF ni tocar cookies.
- El laboratorio local conserva su server action de salida.
- El User Pool privado cierra `SignUp` nativo. La aplicacion sigue requiriendo
  Google mas una invitacion nominal ligada al correo verificado.
- El contrato separa MFA nativo de assurance Google federado y registra la
  decision humana pendiente en `UD-IAM-FEDERATED-MFA`.
- `tools.identity_readiness` consulta cuatro endpoints Cognito mediante AWS CLI
  sin shell y reporta 16 controles sin devolver IDs, usuarios, correo o secretos.
  Incluso en verde mantiene `activation_authorized` y `real_data_authorized`
  en `false`.

## Evidencia local

| Verificacion | Resultado |
|---|---|
| Web unitarias | 43 archivos, 256 pruebas, OK |
| Web typecheck, lint y build Next.js | OK; ruta `/api/auth/oidc/logout` incluida |
| Sonda live/adaptador/CLI | 9 pruebas, OK |
| Contrato private-pilot | 38 pruebas, OK; `errors: []` |
| Work graph | 8 pruebas, OK; FNC-IAM-003 sin orfandad |
| OpenTofu | `fmt -check` y `validate` OK en copia temporal backendless |
| Quality gate | OK sobre cada indice entregado |

## Hallazgos corregidos

1. Logout solo borraba cookies Fincilia y dejaba viva la sesion Hosted UI.
2. El User Pool privado permitia `SignUp` nativo aunque la beta era cerrada.
3. El modelo equiparaba MFA nativo Cognito con MFA federado Google.
4. La primera reserva de FNC-IAM-003 no entro al backlog y el work graph la
   rechazo en CI; `3fc4341` lo corrige y añade una prueba que muerde.

## Pendientes externos

- Aplicar el plano AWS, conectar Google sin llevar el secret a state y ejecutar
  la sonda live.
- Adjudicar `UD-IAM-FEDERATED-MFA` y obtener revisiones independientes.
- DRG-00 sigue `not_met`; ninguna persona ni dato real fue procesado.

## Rollback

Revertir `c0d9ef0`, `3fc4341` y `e0f8154` en ese orden. Como contencion
operativa, dejar `FINCILIA_OIDC_ENABLED=false`, retirar Google del app client y
conservar desired count cero.

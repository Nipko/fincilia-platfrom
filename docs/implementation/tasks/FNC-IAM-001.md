---
id: FNC-IAM-001
title: Inicio de sesión Google mediante IdP administrado
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 93dac84
gate: DRG-00
gate_effect: none
data_ceiling: synthetic_only_until_gate
independent_reviewers: [Security, Privacy/Legal, Architecture, QA]
---

# Resultado

La web ofrece una integración Google OIDC preparada mediante Amazon Cognito,
con Authorization Code + PKCE y scopes mínimos `openid email profile`. Permanece
fail-closed cuando no hay configuración o DRG-00 no autoriza identidad real.

# Criterios de aceptación

1. Botón y rutas de inicio/callback usan `state`, nonce y PKCE S256.
2. Callback URI exacta, HTTPS salvo localhost y cookies transitorias httpOnly.
3. La API no confía en claims del navegador y enlaza el `sub` verificado a un
   `subject_id` interno; empresas y roles continúan resolviéndose server-side.
4. Tokens de Google/Cognito, códigos, correo y secretos no aparecen en URLs
   propias, logs, auditoría, errores o base en claro.
5. Solo se piden `openid email profile`; no Drive ni Gmail. El refresh token
   que Cognito emite obligatoriamente en Authorization Code se descarta en
   memoria: Fincilia no lo usa, registra, devuelve ni persiste.
6. Cuenta nueva completa firma y primera empresa; cuenta existente es idempotente.
7. State/nonce inválidos, token vencido, issuer/audience incorrectos y correo no
   verificado fallan cerrados y no crean filas.
8. Client secret vive en Secrets Manager y nunca en Git ni salida de IaC.
9. Activación real exige DRG-00, revisión independiente y políticas públicas.

# Fuera de alcance

Acceso a APIs de Google, importación de Drive/Gmail, MFA propio, identidad como
fuente de autorización financiera o activar OAuth real antes de DRG-00.

# Evidencia integrada

- Backend y persistencia: `3ec2893`.
- BFF, PKCE y experiencia web: `99c9445`.
- Handoff reproducible: `docs/implementation/handoffs/FNC-IAM-001.md`.
- Runbook de dominio, branding, Google y doble callback:
  `docs/platform/GOOGLE_OAUTH_PUBLICATION.md`.
- Estado: implementación lista para revisión; configuración externa, DRG-00 y
  revisores independientes continúan pendientes.

## Evidencia externa R1 — 2026-08-30

- Google fue configurado como proveedor social en Cognito con scopes mínimos y
  mapeo de `email`, `email_verified`, `name` y `sub`.
- `987778d` integra un cliente Cognito separado para `fincilia.com`, sin secret,
  con callback/logout exactos, Authorization Code, tokens de 15 minutos y
  revocación habilitada.
- El plan OpenTofu produjo `1 add, 0 change, 0 destroy`; el plan posterior fue
  `No changes`. La comprobación directa observó solo Google como IdP.
- La configuración externa deja de estar pendiente. La activación sigue cerrada
  por DRG-00, atestación KMS y revisión independiente.

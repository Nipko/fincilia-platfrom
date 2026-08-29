---
id: FNC-IAM-003
title: Cierre operativo de identidad administrada
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 46d57a3025d7402c7a90b4cb7e8002c50bc02a68
gate: DRG-00
gate_effect: none
data_ceiling: synthetic_only_until_gate
independent_reviewers: [Security, Privacy/Legal, Architecture, QA]
---

# Resultado

La identidad Google/Cognito preparada por FNC-IAM-001 incorpora cierre de
sesión federado, eliminación completa de cookies propias y transitorias, y un
procedimiento reproducible para activar, comprobar y revocar el acceso de una
beta cerrada sin convertir el IdP en fuente de autorización financiera.

# Rutas autorizadas

- `apps/web/src/lib/managed-oidc.ts`, sesión y pruebas relacionadas.
- `apps/web/src/app/api/auth/oidc/logout/**`.
- `apps/web/src/app/empresas/sign-out.tsx` y consumidores estrictamente
  necesarios para el cierre de sesión.
- `apps/web/README.md` y `docs/platform/GOOGLE_OAUTH_PUBLICATION.md`.
- `infra/aws/private-pilot/identity.tf`, contrato y validador del piloto.
- ADR-012 y solicitud de decisión sobre assurance federado.
- Ficha, handoff, trazabilidad y registros centrales por Integration Steward.

# Criterios de aceptación

1. El modo administrado elimina la sesión Fincilia y termina la sesión Hosted
   UI de Cognito mediante un endpoint y `logout_uri` HTTPS exactos.
2. El endpoint solo acepta POST same-origin, no refleja parámetros del cliente
   y construye la redirección desde configuración server-side validada.
3. Se eliminan cookies de sesión, nombre visible y transacción OIDC incluso
   cuando la configuración administrada falla cerrada.
4. El modo local conserva el cierre de sesión interno actual.
5. Logout, callback y autorización no incorporan tokens, correo, invitación,
   subject externo ni secretos en URLs, logs o respuestas.
6. El runbook distingue crear, consumir, listar y revocar invitaciones
   nominales; solo almacena HMAC/digests y nunca el código o correo en claro.
7. Unitarias, tipos, lint, build y CI aplicables quedan verdes.
8. La activación real continúa bloqueada por DRG-00 y revisión independiente.
9. El contrato distingue MFA nativo de assurance federado: nunca afirma que
   Cognito añade MFA a una sesión Google.

# Fuera de alcance

Autorizar datos reales, almacenar contraseñas, usar claims de Google como roles,
acceder a APIs Google, aceptar revisiones humanas o desplegar el plano AWS.

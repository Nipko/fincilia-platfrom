---
task_id: FNC-IAM-002
status: REVIEW_PENDING
base_sha: a1f03c7430e30c15ccf0a3ed411c3baf7d4e26bb
implementation_shas: [72a8630]
tested_head_sha: 4eed9d5
data_ceiling: synthetic_only_until_gate
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Security, Privacy/Legal, Product/UX, Accessibility/QA]
---

# Handoff FNC-IAM-002 — identidad completa dentro del entorno autorizado

## Resultado integrado

La persona autenticada dispone de `/cuenta`: ve su nombre, modo de identidad,
vigencia de sesión, empresas y roles resueltos por el servidor; entra a cada
espacio autorizado, administra equipo solo cuando su permiso lo permite y puede
cerrar sesión explícitamente. El shell lleva siempre al mismo centro de cuenta.

`/me` añade únicamente `identity_mode`, `credential_management`,
`session_issued_at` y `session_expires_at`. No devuelve correo, subject externo,
issuer, token, secreto ni hash. Google/Cognito se presenta como administrado
solo cuando el runtime lo active; el adaptador local se identifica como
demostración sintética y no portable a producción.

## Controles y evidencia

- La autorización y el alcance por empresa siguen resolviéndose server-side y
  bajo RLS; la vista no acepta `company_id` como autoridad.
- Un 401 redirige al acceso; un 403 no enumera otra identidad ni empresa.
- 29 pruebas reales API/PostgreSQL pasaron, incluidas respuesta mínima de
  `/me`, token ausente/caducado y denegación cross-company.
- La página tiene 2 unitarias, 1 recorrido Chromium y 1 análisis Axe focal; el
  conjunto web pasó 249 pruebas, lint, TypeScript y build de producción.
- La inspección visual se realizó sobre el stack local sano y sintético.

## Límites y revisión requerida

No se activaron Google real, MFA, recuperación de contraseña, correo ni datos
reales. Esas capacidades pertenecen al IdP administrado preparado por
FNC-IAM-001 y continúan bloqueadas por DRG-00, configuración de dominio/Google y
revisión independiente. Security revisa exposición y expiración; Privacy/Legal,
minimización; Product/UX y Accessibility/QA, claridad y uso asistido.

## Rollback

Revertir `72a8630` retira `/cuenta` y los metadatos adicionales de `/me` sin
cambiar credenciales, grants, RLS, migraciones ni sesiones persistidas. Las
rutas quedan liberadas con este handoff.

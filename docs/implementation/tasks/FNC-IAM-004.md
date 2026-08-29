---
id: FNC-IAM-004
title: Alta publica definitiva con Google y aceptacion legal versionada
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: 08762c5318ec7132fac0c9f21ef9b79e066cfb17
gate: DRG-00
gate_effect: none
data_ceiling: synthetic_only_until_gate
independent_reviewers: [Security, Privacy/Legal, Database/Architecture, Product/UX, QA]
---

# Resultado

Una persona puede registrarse publicamente mediante Google, crear
atomicamente su sujeto interno, firma y membresia `owner`, conservar evidencia
versionada de terminos y privacidad y continuar al alta de su primera empresa.
No existen codigos de invitacion en el recorrido definitivo.

# Decisiones de alcance

- Google/Cognito autentica; PostgreSQL sigue siendo la unica autoridad de
  membresias, empresas, roles y permisos.
- El registro nativo de Cognito permanece cerrado. Alta publica Google no
  significa almacenar passwords en Fincilia.
- `login` nunca crea una cuenta desconocida. Solo `register`, con terminos y
  privacidad actuales aceptados, puede materializarla.
- Correo y `sub` se convierten en referencias HMAC antes de PostgreSQL.
- El modo de alta `public_google` es un control operativo permanente y puede
  cerrarse sin retirar el login de cuentas existentes.
- Esta tarea no afirma MFA para Google y no autoriza datos reales.

# Rutas

- `db/migrations/V0043*` y pruebas PostgreSQL de identidad.
- `apps/api/src/fincilia_api/oidc.py`, contrato HTTP y settings relacionados.
- `apps/web/src/lib/managed-oidc.ts`, registro, callback y pruebas.
- `infra/aws/private-pilot` exclusivamente para configurar el recorrido final.
- Contratos, runbook, ADR-012, CI, trazabilidad y handoff.

# Criterios de aceptacion

1. Registro Google publico sin invitacion y con Code + PKCE, state y nonce.
2. Login de una identidad desconocida no crea filas y dirige al registro.
3. Alta atomica de sujeto, binding HMAC, firma, owner y dos aceptaciones legales.
4. Solo versiones legales activas pueden aceptarse; versiones obsoletas fallan
   sin estado parcial.
5. Una referencia de correo verificado no crea dos identidades internas.
6. El runtime ejecuta solo resolucion y alta publica; la funcion antigua de
   invitacion queda revocada.
7. El registro redirige a `/empresas/nueva`; login a `/empresas`.
8. El control `disabled|public_google` falla cerrado y queda tipado en API,
   web, IaC y contrato runtime.
9. Unitarias, PostgreSQL, tipos, lint, build y CI quedan verdes.
10. Dominio, Google Production, AWS apply, datos reales y revisiones humanas
    permanecen como activaciones separadas.

# Rollback

- Operativo: fijar `FINCILIA_OIDC_REGISTRATION_MODE=disabled`; las cuentas ya
  creadas conservan login y no se destruyen datos.
- Esquema: forward-only. V0043 no se edita despues de integrar; una correccion
  usa una nueva migracion.

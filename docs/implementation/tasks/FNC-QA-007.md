---
task: FNC-QA-007
title: Administracion final de usuarios y roles por empresa
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: 34cdb64
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Security, QA, Web/UX]
---

# Resultado esperado

Un owner o firm_admin administra roles de miembros existentes en cada empresa. La
identidad se aprovisiona mediante el IdP —y mediante la semilla solo en local—; Fincilia
asigna y revoca concesiones company-scoped sin crear contrasenas propias.

## Rutas reservadas

- `apps/api/src/fincilia_api/access.py`
- `apps/api/src/fincilia_api/routes.py`
- `apps/api/tests/**` solo si aplica al contrato HTTP
- `db/tests/test_member_roles.py`
- `apps/web/src/app/actions.ts`
- `apps/web/src/app/__tests__/actions.test.ts`
- `apps/web/src/app/empresas/**`
- `apps/web/src/lib/api.ts`
- `apps/web/src/app/globals.css`
- `apps/web/tests/e2e/member-roles.spec.ts`
- ficha, handoff y archivos centrales de integración.

## Criterios de aceptación

1. `member.manage` es obligatorio y se resuelve server-side para listar y mutar roles.
2. La lista solo contiene miembros activos de la firma delegada y sus roles en la
   empresa actual; no expone email, credenciales ni membresias de otras firmas.
3. Owner puede conceder/revocar todos los roles; firm_admin no puede conceder ni
   revocar owner o firm_admin.
4. Nadie puede concederse un rol a si mismo.
5. Revocar el ultimo owner activo se rechaza bajo bloqueo transaccional.
6. Conceder y revocar son idempotentes, auditados y elevan authorization_version.
7. Una misma persona puede acumular roles; SoD por objeto sigue impidiendo revisar su
   propia preparacion.
8. La web permite asignar y revocar con motivo y explica los limites.
9. PostgreSQL real, unitarias web y E2E prueban permisos, tenancy, revocacion de sesion,
   ultimo owner y ausencia de PII.
10. No se crean contrasenas ni autenticacion productiva propia.

## Verificación

```text
npm run typecheck
npm run lint
npm run test:unit
python -m unittest db.tests.test_member_roles -v
npm run test:e2e -- member-roles.spec.ts
python -m tools.work_graph.validate
python -m tools.quality_gate.cli
```

## Evidencia de entrega

La implementacion y los resultados reproducibles se consolidan en
`docs/implementation/handoffs/FNC-QA-007.md`. Security, QA y Web/UX permanecen
como revisores independientes; esta tarea no modifica S1-READY ni los data gates.

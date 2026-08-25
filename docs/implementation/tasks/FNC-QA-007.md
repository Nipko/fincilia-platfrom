---
task: FNC-QA-007
title: Selector local de personas sinteticas multirrol
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 34cdb64
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Security, QA, Web/UX]
---

# Resultado esperado

Una sola persona fisica puede recorrer en local las capacidades de owner, preparer,
reviewer y auditor seleccionando identidades sinteticas. El cambio de persona crea una
sesion normal contra la API y nunca fusiona actores, permisos ni auditoria.

## Rutas reservadas

- `apps/web/src/app/entrar/**`
- `apps/web/src/app/actions.ts`
- `apps/web/src/app/__tests__/actions.test.ts`
- `apps/web/src/app/empresas/**` solo para el acceso al selector
- `apps/web/src/lib/demo-personas.ts`
- `apps/web/src/app/globals.css`
- `apps/web/tests/e2e/demo-personas.spec.ts`
- `infra/local/compose.yaml`
- `.env.example`
- `docs/platform/runtime-config.json`
- `tools/runtime_config/**` solo si la nueva configuracion exige cobertura
- ficha, handoff y archivos centrales de integración.

## Criterios de aceptación

1. El selector solo aparece con `FINCILIA_ENV=local`, datos reales deshabilitados y
   un feature gate local explícito.
2. El navegador nunca recibe ni envía la contraseña común de demo desde el selector.
3. La server action acepta únicamente cuatro claves de persona en allowlist.
4. Cada selección obtiene un token normal de la API y sobrescribe la cookie httpOnly.
5. Owner, preparer, reviewer y auditor conservan `subject_id` distintos.
6. El portafolio muestra acceso para cambiar de persona y la identidad activa.
7. Una configuración no local o de datos reales falla cerrada aunque el feature gate
   esté activo.
8. Unitarias y E2E cubren selección, cambio de persona, rol visible y no exposición del
   secreto.
9. No cambia RLS, RBAC, SoD, migraciones ni permisos productivos.

## Verificación

```text
npm run typecheck
npm run lint
npm run test:unit
npm run test:e2e -- demo-personas.spec.ts
python -m tools.runtime_config.validate
python -m tools.work_graph.validate
python -m tools.quality_gate.cli
```

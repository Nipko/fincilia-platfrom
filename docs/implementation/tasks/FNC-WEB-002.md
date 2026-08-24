---
id: FNC-WEB-002
alias: FNC-P4.2
title: Puesto web de revision y excepciones de dataset
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: bf0c023
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Product, Accounting, Security, Accessibility/QA]
---

# Resultado esperado

La persona revisora ve por que un dataset puede o no publicarse, inspecciona los
overrides vigentes, aprueba una excepcion critica que preparo otra persona o
rechaza el dataset con motivo. La API es la autoridad del readiness y la web no
infiere permisos, estados financieros ni segregacion de funciones.

Es una rebanada local sintetica. No habilita cierre, auto-match, reportes
certificados, datos reales ni aplicacion movil, y no mueve S1-READY.

# Definition of Ready

- FNC-WEB-001 y FNC-API-001 tienen handoff y evidencia verde.
- Los endpoints de listar/crear/aprobar overrides y rechazar dataset ya existen.
- El contrato de override inmutable, su aprobacion independiente y el bloqueo de
  publicacion ya estan implementados en PostgreSQL.
- No se requiere migracion, permiso nuevo ni cambio de semantica financiera.

# Rutas permitidas

- `apps/api/src/fincilia_api/datasets.py`
- `apps/api/src/fincilia_api/routes.py`
- `apps/web/src/app/actions.ts`
- `apps/web/src/lib/api.ts`
- `apps/web/src/app/empresas/[companyId]/documentos/[artifactId]/mapeo/**`
- `apps/web/src/app/__tests__/actions.test.ts`
- `apps/web/src/app/__tests__/route-boundaries.test.tsx`
- `db/tests/test_row_overrides.py`
- `db/tests/test_p3_vertical.py` solo si la regresion de readiness lo exige.
- Ficha, handoff y registro/liberacion central por Integration Steward.

# Rutas prohibidas

- Migraciones, seeds, permisos, RLS y esquema canonico.
- Mobile, worker, conectores, exportaciones y CI.
- ADR, gates y contratos compartidos.
- Valores reales, secretos, IA y datos financieros reales.

# Criterios de aceptacion

- **AC-01.** `GET dataset` devuelve blockers de publicacion calculados server-side
  y `can_publish` nunca es verdadero si uno aplica.
- **AC-02.** Estado, SoD, release y overrides usan una unica funcion de dominio;
  la lectura y el POST de publicacion no pueden divergir.
- **AC-03.** Un override critico pendiente aparece en la web sin mostrar valores;
  se muestran campo, clase, motivo, autor y estado de aprobacion.
- **AC-04.** Aprobar exige `dataset.publish`, verifica que el override pertenece al
  dataset mostrado y conserva SoD aunque una persona tenga ambos permisos.
- **AC-05.** Tras aprobar, la vista se revalida y el readiness cambia sin editar
  ni borrar el override.
- **AC-06.** El revisor puede rechazar un dataset validado con motivo obligatorio;
  la web verifica que el dataset pertenece al documento visible.
- **AC-07.** 401 redirige; 403, 409 y 422 producen mensajes diferenciados y no
  convierten errores en exito o listas vacias.
- **AC-08.** Formularios tienen etiquetas, feedback accesible, estado pendiente y
  no contienen digests ni valores financieros ocultos.
- **AC-09.** Pruebas de dominio PostgreSQL, acciones web, tipos, lint y build pasan.
- **AC-10.** Ningun gate, permiso, migracion o aplicacion movil cambia.

# Verificacion

```bash
docker compose -f infra/local/compose.yaml -p fincilia-local --profile migrate \
  run --rm migrate python -m unittest db.tests.test_row_overrides -v
cd apps/web
npm run lint
npm run typecheck
npm run test:unit
npm run build
cd ../..
python -B -m tools.work_graph.validate
python -B -m tools.test_catalog.cli validate
python -B -m tools.quality_gate.cli
```

# Definition of Done

- AC-01..AC-10 tienen evidencia reproducible y handoff.
- Product/Accounting, Security y Accessibility/QA quedan como revisores
  independientes pendientes o registrados.
- Estado final `review_pending`; rutas liberadas y S1-READY sin cambios.

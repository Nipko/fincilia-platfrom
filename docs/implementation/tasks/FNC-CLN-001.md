---
id: FNC-CLN-001
alias: FNC-P4.4
title: Propuestas tipadas de correccion por fila
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: 595fcad
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Accounting, Security, Database, Product, QA]
---

# Resultado esperado

Un preparador puede proponer la correccion tipada de un campo canónico de un
dataset validado, y un revisor independiente puede aprobarla o rechazarla. La
propuesta no altera raw, source records ni movimientos canónicos, y una
correccion pendiente o aprobada pero aun no aplicada bloquea la publicación del
dataset base.

Esta rebanada local y sintética materializa propuesta y revisión. La aplicación
determinística sobre una **nueva** versión del dataset, con su
`lineage_row_override`, queda separada en FNC-CLN-002. Aprobar no equivale a
aplicar y la interfaz debe decirlo expresamente.

# Definition of Ready

- ADR-006 y `LINEAGE_SPEC.md` definen overlay append-only, concurrencia
  optimista, valores tipados y segregación de funciones.
- ADR-024 y V0012 separan una propuesta con valor de la evidencia digest-only de
  una desviación ya aplicada.
- FNC-WEB-002 aporta puesto de revisión y publicación con blockers server-side.
- Base `595fcad`, worktree limpio y solo datos sintéticos autorizados.

# Rutas permitidas

- `docs/adr/ADR-026-staged-field-overlay.md`
- `docs/adr/README.md`
- `db/migrations/V0016__staged_field_overlay.sql`
- `db/tests/test_field_overlays.py`
- `apps/api/src/fincilia_api/corrections.py`
- `apps/api/src/fincilia_api/main.py`
- `apps/api/src/fincilia_api/datasets.py`
- `apps/api/tests/test_corrections.py`
- `apps/web/src/app/empresas/**/correcciones/**`
- `apps/web/src/app/empresas/**/movimientos/**`
- `apps/web/src/app/empresas/**/mapeo/**`
- `apps/web/src/app/empresas/**/__tests__/**`
- `apps/web/src/app/actions.ts`
- `apps/web/src/app/__tests__/actions.test.ts`
- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/corrections.ts`
- `apps/web/src/lib/__tests__/corrections.test.ts`
- `apps/web/src/app/globals.css`
- ficha, handoff y registros centrales por Integration Steward.

# Rutas prohibidas

- Raw, objetos originales, source records y movimientos canónicos existentes.
- Workers, conectores, móvil, IA, auto-match, cierre e informes certificados.
- ADR Accepted, contratos compartidos, gates y datos reales.
- Aplicar una propuesta o crear una nueva versión de dataset en esta rebanada.

# Criterios de aceptación

- **AC-01.** El servidor resuelve empresa, dataset, movimiento y source record;
  no confía en `company_id`, `source_record_id` ni digest resultante del cliente.
- **AC-02.** Solo un dataset `validated` acepta propuestas y solo para campos
  canónicos permitidos con parseo determinístico: decimal exacto, ISO date,
  moneda ISO de tres letras y dirección cerrada.
- **AC-03.** `expected_base_digest` implementa concurrencia optimista; una base
  stale o un no-op devuelve conflicto estable y no persiste nada.
- **AC-04.** Propuesta y revisión son append-only, company-scoped, con RLS
  forzada, sin UPDATE/DELETE para la aplicación.
- **AC-05.** Los campos críticos exigen revisor diferente del autor y permiso
  `dataset.publish`; aprobar o rechazar dos veces es conflicto estable.
- **AC-06.** Pendiente y aprobada-sin-aplicar bloquean publicación; rechazada no
  modifica el dataset ni lo bloquea.
- **AC-07.** La web muestra valor actual, propuesta, autor, motivo, estado y la
  diferencia entre aprobada y aplicada. No afirma que el movimiento cambió.
- **AC-08.** Lectura y mutación cross-company responden de forma neutral y nunca
  revelan existencia.
- **AC-09.** Dinero nunca usa float; comentarios y errores no llegan a logs ni
  auditoría como valores financieros.
- **AC-10.** Pruebas puras, web, PostgreSQL real, lint, tipos, build, quality gate
  y handoff reproducible pasan.

# Verificación

```bash
python -m unittest apps.api.tests.test_corrections -v
docker compose -f infra/local/compose.yaml -p fincilia-local --profile migrate run --rm migrate python -m unittest db.tests.test_field_overlays -v
cd apps/web && npm run lint && npm run typecheck && npm run test:unit && npm run build
python -B -m tools.work_graph.validate
python -B -m tools.test_catalog.cli validate
python -B -m tools.quality_gate.cli
```

# Definition of Done

- AC-01..AC-10 con evidencia y rollback documentado.
- ADR-026 queda `Proposed`; no se inventa aprobación de persistencia.
- Revisores independientes quedan pendientes y S1-READY no cambia.
- FNC-CLN-002 queda como siguiente rebanada explícita, no como comportamiento
  implícito ni TODO sin owner.

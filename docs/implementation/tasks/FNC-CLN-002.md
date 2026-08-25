---
id: FNC-CLN-002
title: Aplicacion reproducible de correcciones aprobadas
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 97d9122
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Accounting, Security, Database, Product, QA]
---

# Resultado

Aplicar atomica y deterministicamente todas las correcciones aprobadas de un
dataset validado a una nueva version, sin mutar evidencia, movimientos ni
versiones anteriores. La version derivada conserva el artefacto y plan de
transformacion, crea nuevos registros y movimientos, registra el conjunto exacto
de overlays y agrega un `lineage_row_override` digest-only por campo corregido.

# Definition of Ready

- FNC-CLN-001 entrega propuestas tipadas y revision SoD append-only.
- ADR-024 y ADR-026 exigen version nueva, overlay aprobado y linaje por fila.
- V0012 y V0016 estan integradas; PostgreSQL 17 local usa solo datos sinteticos.
- Base `97d9122`, worktree limpio e Integration Steward como unico ejecutor Git
  y Database Migration Owner de esta rebanada.

# Rutas reservadas

- `db/migrations/V0023__apply_approved_field_overlays.sql`
- `db/tests/test_correction_application.py`
- `apps/api/src/fincilia_api/correction_application.py`
- `apps/api/src/fincilia_api/main.py`
- `apps/api/tests/test_correction_application.py`
- `apps/web/src/lib/api.ts`
- `apps/web/src/app/actions.ts`
- `apps/web/src/app/__tests__/actions.test.ts`
- `apps/web/src/app/empresas/[companyId]/documentos/[artifactId]/mapeo/**`
- ficha, handoff y registros centrales por Integration Steward.

# Criterios de aceptacion

- **AC-01.** La empresa y el dataset se resuelven server-side con RLS y
  `dataset.map`; una empresa ajena recibe respuesta neutral.
- **AC-02.** Solo un dataset `validated` con una o mas propuestas `approved` y
  ninguna pendiente acepta aplicacion. Una propuesta rechazada se excluye.
- **AC-03.** Una transaccion y un lock por dataset crean un nuevo processing run,
  dataset, source records, movimientos, links, manifest y overrides. Un fallo no
  deja una version parcial.
- **AC-04.** Raw, dataset base, source records, movimientos, propuestas y
  revisiones anteriores permanecen byte/logicamente inmutables.
- **AC-05.** Cada valor aplicado se vuelve a normalizar y su digest debe coincidir
  con lo aprobado y con la huella base vigente. Drift falla cerrado.
- **AC-06.** El dataset derivado queda `validated`, nunca publicado; publicar
  exige otra persona por la regla SoD existente.
- **AC-07.** El manifiesto fija dataset base, conjunto ordenado de overlays y su
  digest. Cada correccion aplicada queda en una tabla append-only y en
  `lineage_row_override` sin copiar el valor.
- **AC-08.** Repetir o competir por la aplicacion devuelve de forma idempotente la
  misma version o conflicto estable; nunca duplica movimientos.
- **AC-09.** La web explica que se crea una version nueva, muestra el resultado y
  navega a ella; no afirma publicacion, conciliacion ni cierre.
- **AC-10.** Pruebas puras, PostgreSQL real, API/web, lint, tipos, build, quality
  gate, migracion repetible y handoff pasan.

# Limites

Solo datos sinteticos. Sin mutacion destructiva, auto-match, cierre, IA, movil,
conectores reales ni publicacion automatica. ADR-026 y revisiones independientes
permanecen pendientes; esta tarea no mueve S1-READY.

# Verificacion

```powershell
python -m unittest apps.api.tests.test_correction_application -v
docker compose -f infra/local/compose.yaml -p fincilia-local --profile migrate run --rm migrate python -m unittest db.tests.test_correction_application -v
Set-Location apps/web; npm run lint; npm run typecheck; npm run test:unit; npm run build
python -B -m tools.work_graph.validate
python -B -m tools.test_catalog.cli validate
python -B -m tools.migration_readiness.validate
python -B -m tools.quality_gate.cli
```

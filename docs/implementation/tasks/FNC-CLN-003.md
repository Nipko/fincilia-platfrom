---
id: FNC-CLN-003
title: Aplicabilidad de correcciones ligada al plan de linaje
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 4654c3b
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Accounting, Security, Product, QA]
---

# Resultado

Impedir que una persona proponga una corrección que el dataset no pueda aplicar
de forma reproducible. Los campos ofrecidos se derivan del plan de linaje real
de la versión y una petición manipulada se rechaza antes de crear el overlay.

# Definition of Ready

- FNC-CLN-001 y FNC-CLN-002 están integradas y conservan propuesta/aplicación
  como etapas distintas.
- ADR-026 exige tipos cerrados, linaje y dataset base inmutable.
- Base `4654c3b`, árbol limpio y datos exclusivamente sintéticos.

# Rutas reservadas

- `apps/api/src/fincilia_api/corrections.py`
- `apps/api/tests/test_correction_application.py`
- `db/tests/test_correction_application.py`
- `db/tests/test_field_overlays.py`
- `apps/web/src/app/empresas/[companyId]/movimientos/[movementId]/page.tsx`
- pruebas web directamente relacionadas si son necesarias.
- ficha, handoff y registros centrales por Integration Steward.

# Criterios de aceptación

- **AC-01.** `correction-targets` solo devuelve campos cuyo plan tiene las seis
  etapas requeridas, exactamente una vez y en orden.
- **AC-02.** Proponer un campo soportado por tipo pero ausente/incompleto en el
  plan recibe conflicto estable y no crea overlay.
- **AC-03.** La decisión usa `dataset.lineage_plan_id` bajo el contexto RLS; no
  confía en campos, pasos ni locators enviados por cliente.
- **AC-04.** Un dataset sin plan o con plan incompleto no expone un target falso.
- **AC-05.** La web explica que solo aparecen campos aplicables y conserva el
  flujo actual de propuesta, revisión y aplicación para los campos válidos.
- **AC-06.** Pruebas puras, PostgreSQL/API, web, quality gate y handoff pasan.

# Límites

No amplía el modelo canónico ni inventa pasos de linaje. No habilita datos
reales, IA, móvil, auto-match, cierre o publicación automática. Expandir un plan
histórico requiere otra versión de mapping/engine y revisión independiente.

---
id: FNC-CLS-004
title: Preparacion de cierre integrada con conciliacion de saldos
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 020a7be
integration_sha: pending
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Accounting, Security, Backend/Architecture, Product, Accessibility/QA]
---

# Resultado esperado

Eliminar la desconexion entre el diagnostico de preparacion de cierre y los
estados reproducibles que FNC-CLS-003 ya materializa. Por empresa y periodo, la
plataforma debe comprobar cobertura de cuentas y el ultimo statement autorizado,
para distinguir evidencia bloqueada de evidencia lista para revision humana.

`ready_for_review` no significa `ready_to_close`: no acepta excepciones, no aplica
materialidad, no firma, no certifica, no cambia el ciclo y no ejecuta un cierre.

# Dependencias y autoridad

- FNC-CLS-001 aporta la proyeccion company-scoped y fail-closed.
- FNC-CLS-002 aporta saldos canonicos con moneda y linaje.
- FNC-CLS-003 aporta assessments, statements y decisiones append-only.
- FNC-DOM-003 define completitud y ecuacion de conciliacion de saldos.
- La seccion 10.1 del plan unificado define condiciones de cierre; esta tarea
  solo materializa evidencia previa y mantiene la operacion de cierre bloqueada.

# Rutas reservadas

- `apps/api/src/fincilia_api/close_readiness.py`, `routes.py` y pruebas focales.
- `db/tests/test_close_readiness.py`.
- `db/tests/test_balance_reconciliation_statements.py` (solo aserciones de
  integracion read-only sobre el fixture existente).
- `apps/web/src/lib/close-readiness.ts`, tipos API y pruebas focales.
- `apps/web/src/app/preparacion-cierre/**`, estilos y navegacion relacionada.
- `apps/web/tests/e2e/close-readiness*.spec.ts`.
- Ficha, handoff, backlog y fase vigente por Integration Steward.

# Criterios de aceptacion

- **AC-01.** La seleccion del statement es company/account/period-scoped,
  determinista y versionada; nunca usa un ultimo global ni datos del cliente.
- **AC-02.** Cada cuenta esperada queda cubierta exactamente una vez. Sin cuenta,
  assessment verificado o statement vigente elegible, el periodo falla cerrado.
- **AC-03.** Solo un statement `balanced`, reproducible y ligado a assessments
  elegibles satisface el control. `review_required`, evidencia stale o versiones
  incompletas mantienen el bloqueo.
- **AC-04.** Un periodo con todos los controles diagnosticos en verde se rotula
  `ready_for_review`; `close_ready` y `can_execute_close` permanecen siempre falsos.
- **AC-05.** La proyeccion no agrega ni expone importes. Devuelve conteos,
  identificadores, estados y razones explicables bajo `close.prepare` y RLS.
- **AC-06.** La web muestra cobertura por cuenta y vinculos a evidencia, separa
  claramente revision humana de cierre, y no incorpora boton de cerrar, certificar
  o aceptar materialidad.
- **AC-07.** Unitarias API/web, PostgreSQL cross-company, E2E, Axe, lint, tipos,
  build, quality gate y handoff quedan verdes y reproducibles.

# Limites y rollback

No modifica migraciones, estados financieros, statements, balances, ciclos,
permisos, IA, movil, datos reales, ADR ni gates. El rollback retira la lectura y
la presentacion integrada; no revierte ledgers ni elimina evidencia.

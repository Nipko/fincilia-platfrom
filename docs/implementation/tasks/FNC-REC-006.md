---
id: FNC-REC-006
title: Expediente histórico de conciliación direccionable y company-scoped
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 9dd1759817cbc91cc61a8ee117df920c3be37984
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Security, Backend/Architecture, Product, Accessibility/QA]
---

# Resultado esperado

Permitir que un expediente append-only de conciliación siga siendo consultable
por su identificador estable desde la bandeja multiempresa aunque sus datasets
ya no sean elegibles para generar candidatos nuevos o no aparezca en la página
actual. La vista no reactiva datasets, recalcula candidatos, modifica decisiones
ni afirma que exista una conciliación de saldos.

# Autoridad

- ADR-027 conserva candidato y decisión como historia append-only y exige que el
  estado visible se derive del ledger, no de una lista efímera de candidatos.
- FNC-REC-003 enlaza la bandeja al expediente, pero hoy el enlace depende de que
  ambos datasets continúen elegibles y de que el candidato esté en la página 0.
- El cambio es expand-only y read-only: agrega una lectura exacta company-scoped
  y una representación histórica; no cambia semántica financiera ni esquema.

# Rutas reservadas

- `apps/api/src/fincilia_api/reconciliation.py`, `routes.py` y pruebas focales.
- `db/tests/test_reconciliation_decisions.py` para el contrato HTTP/RLS real.
- `apps/web/src/lib/api.ts`, `reconciliation.ts`, bandeja y estación web.
- pruebas unitarias, E2E y Axe de conciliación.
- esta ficha, handoff y registros centrales por Integration Steward.

# Fuera de alcance

- Reabrir, revertir, reasignar o borrar decisiones.
- Hacer elegible un dataset histórico o recalcular reglas antiguas.
- Cambiar confirmación, exclusividad, grupos, saldos o cierre.
- Migraciones, datos reales, IA, conectores externos o móvil.

# Criterios de aceptación

- **AC-01.** `GET .../reviews/{candidate_id}` exige `movement.read`, contexto de
  empresa resuelto server-side y RLS; recurso ajeno o inexistente falla neutral.
- **AC-02.** La lectura devuelve el ledger exacto y sus IDs de evidencia aunque
  los datasets ya no sean elegibles; no ejecuta el motor de candidatos.
- **AC-03.** La bandeja enlaza el `candidate_id` en la URL y la estación valida
  su forma antes de solicitarlo, sin confiar en IDs de empresa del cliente.
- **AC-04.** Si el candidato no está en la página visible, aparece una sección
  histórica con estado, actor, tiempo y enlaces a ambos movimientos.
- **AC-05.** La sección declara que no reactiva evidencia, no prueba saldos y no
  tiene efecto financiero. Los controles existentes dependen de permisos API.
- **AC-06.** Un expediente ya visible como candidato no se duplica.
- **AC-07.** API, web, E2E, Axe, lint, tipos, build y quality gate pasan; no se
  promueve ADR-027, S1-READY ni una revisión humana.

# Rollout y rollback

Rollout local con datos sintéticos. El rollback retira endpoint, parámetro y
sección histórica; ningún ledger o dato debe borrarse o reescribirse.

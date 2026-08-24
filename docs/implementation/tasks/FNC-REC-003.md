---
id: FNC-REC-003
alias: FNC-P4.8
title: Bandeja multiempresa de revision de conciliaciones
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: 49339a04511fd459f1a38566654ca0d32a4453fd
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Product/Accounting, Security, Backend/Architecture, Accessibility/QA]
---

# Resultado esperado

Un contador con acceso a varias empresas puede ver en una sola bandeja los
expedientes de conciliacion que requieren revision, filtrarlos por estado y
volver al par exacto que contiene su evidencia. La agregacion conserva la
frontera `company`: la web consulta cada empresa por separado y una revocacion,
un 403 o un fallo parcial nunca se convierte en cero trabajo.

# Autoridad y limites

- FNC-REC-002 sigue siendo la unica autoridad para proponer y decidir.
- La bandeja es una proyeccion operativa; no agrega importes, no calcula saldos,
  no confirma candidatos y no representa una conciliacion terminada.
- Cada consulta pasa por `company_context`, permisos server-side y una sesion
  PostgreSQL con RLS. No se introduce una lectura cross-company privilegiada.
- ADR-027 permanece `Proposed`; S1-READY y los gates de datos no se mueven.

# Definition of Ready

- Base declarada integrada, arbol limpio y CI verde.
- FNC-REC-002 disponible con ledger append-only y revision company-scoped.
- Integration Steward reserva API, web, pruebas y registros de la tarea.
- No se requieren migraciones, datos reales, IA, servicios externos ni movil.

# Rutas permitidas

- `apps/api/src/fincilia_api/reconciliation.py` y `routes.py`.
- `apps/api/tests/**` y `db/tests/test_reconciliation_decisions.py`.
- `apps/web/src/**` y `apps/web/tests/**`.
- Ficha, handoff y registros centrales por Integration Steward.

# Rutas prohibidas

- Migraciones y mutaciones del ledger FNC-REC-002.
- Auto-match, cierre, balances certificados, tolerancias o agregacion monetaria.
- Lecturas con `BYPASSRLS`, identidad confiada al cliente o endpoints firm-wide.
- Workers, conectores, IA, movil, datos reales y ADR Accepted.

# Criterios de aceptacion

- **AC-01.** La API lista expedientes de una sola empresa con filtros cerrados
  `open`, `confirmed`, `rejected` o `all`, offset/limit acotados y orden estable.
- **AC-02.** Dataset IDs se derivan server-side de los movimientos persistidos;
  la respuesta permite volver al par exacto sin exponer importes ni referencias.
- **AC-03.** Filtros invalidos fallan cerrados; IDs ajenos, acceso revocado y
  ausencia de permiso conservan respuestas neutrales.
- **AC-04.** La web consulta empresa por empresa con concurrencia acotada. Un 401
  termina la sesion; 403/revocacion/fallo parcial se muestran explicitamente.
- **AC-05.** La bandeja ordena trabajo sin sumar dinero, distingue pendiente de
  resuelto y advierte siempre que una confirmacion no prueba saldos ni cierre.
- **AC-06.** Cada item identifica empresa, estado, proponente, instante UTC,
  distancia temporal y reglas; el enlace abre el expediente exacto.
- **AC-07.** Roles sin `movement.read` no reciben datos; las acciones siguen en
  la estacion FNC-REC-002 y la UI no reconstruye autorizacion.
- **AC-08.** Unitarias API/web, PostgreSQL cross-company, E2E reviewer, Axe,
  lint, tipos, build, quality gate, handoff y CI pasan sobre el head entregado.

# Rollout y rollback

Solo entorno local sintetico. El rollback elimina el endpoint de proyeccion y la
ruta `/revisiones`; no toca propuestas, decisiones ni auditoria existentes.

# Definition of Done

- AC-01..AC-08 con evidencia reproducible y commits incrementales.
- Sin migracion ni efecto financiero; ADR-027 permanece Proposed.
- Rutas liberadas, handoff `REVIEW_PENDING` y CI verde.

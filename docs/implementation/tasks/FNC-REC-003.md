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

# Ronda R2 — productividad y continuidad de la bandeja

Base: `796b62d46c34676b32df47b072cd08628915ff2c`. La ronda conserva el mismo
alcance y agrega los siguientes criterios sin modificar el ledger ni la API:

- **AC-R2-01.** El usuario filtra por una empresa autorizada o por todo su
  portafolio; un ID desconocido, repetido o una pagina invalida falla cerrado y
  nunca se convierte silenciosamente en todas las empresas.
- **AC-R2-02.** Una empresa seleccionada pagina de 50 en 50 hasta offset 10000,
  conservando estado y empresa en cada enlace. La vista multiempresa no simula
  una paginacion global: ante truncamiento exige elegir empresa.
- **AC-R2-03.** La carga visible se resume por empresa sin importes ni saldos y
  el siguiente pendiente es siempre el expediente visible mas antiguo.
- **AC-R2-04.** Abrir un expediente incorpora exclusivamente un contexto de
  retorno cerrado (`estado`, empresa actual o `todas`, pagina acotada). No se
  acepta una URL de retorno arbitraria ni una empresa distinta.
- **AC-R2-05.** Chromium recorre filtro, expediente y retorno; Axe no reporta
  violaciones en la bandeja seleccionada y el laboratorio efimero queda limpio.

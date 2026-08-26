---
id: FNC-CLS-005
title: Expediente inmutable de revision previa al cierre
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: 90997d4
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Accounting, Security, Database, Backend/Architecture, Product, Accessibility/QA]
---

# Resultado esperado

Convertir el diagnostico de FNC-CLS-004 en un expediente versionado y revisable
por empresa y periodo. El preparador fija una manifestacion digest-only de la
evidencia observada, asigna un revisor elegible y el revisor registra una unica
decision append-only: evidencia revisada o cambios solicitados.

Esta tarea no crea `close_snapshot`, no cambia el estado de un ciclo, no firma,
no certifica saldos, no acepta materialidad y no ejecuta ni habilita un cierre.
`evidence_reviewed` significa solamente que una persona distinta reviso la
misma evidencia diagnostica que fue fijada en el expediente.

# Dependencias y autoridad

- ADR-014 y `COMPLETENESS_BALANCES.md` definen completitud, saldos y condiciones
  fail-closed; esta rebanada no modifica su semantica.
- FNC-CLS-004 aporta el diagnostico exacto `blocked|ready_for_review` y mantiene
  `close_ready=false` y `can_execute_close=false`.
- FNC-LIN-001 aporta identificadores, versiones y huellas de linaje sin valores.
- FNC-SEC-001 separa `close.prepare` de `close.approve`; poseer ambos permisos
  nunca permite revisar el trabajo propio.
- No hace falta un ADR nuevo: es un flujo local reversible de revision de la
  evidencia ya definida por ADR-014, sin nueva fuente de verdad ni efecto
  financiero. Cualquier cierre o snapshot si requiere una decision posterior.

# Rutas reservadas

- `db/migrations/V0034__close_review_packet.sql`.
- `db/tests/test_close_review_packets.py` y pruebas de plan focales.
- `apps/api/src/fincilia_api/close_review.py`, `routes.py` y pruebas focales.
- `apps/web/src/lib/close-review.ts`, tipos/cliente API y pruebas focales.
- `apps/web/src/app/preparacion-cierre/**` y estilos relacionados.
- `apps/web/tests/e2e/close-review*.spec.ts`.
- Esta ficha, handoff, backlog, fase vigente y grafo por Integration Steward.

# Rutas prohibidas

- `closed_snapshot`, estado de ciclos, informes certificados, materialidad,
  excepciones contables, auto-match o cualquier efecto sobre movimientos/saldos.
- Datos reales, IA, conectores externos, movil, autenticacion propia y gates.
- Relajar RLS, SoD, auditoria, linaje o permisos para hacer pasar una prueba.

# Criterios de aceptacion

- **AC-01.** El expediente fija empresa, periodo, version, preparador, revisor,
  manifestacion canonica y SHA-256. La manifestacion solo contiene estados,
  conteos, IDs y versiones; nunca importes, monedas, nombres aportados por
  documentos ni valores de celdas.
- **AC-02.** Preparar exige `close.prepare`; la lista estrecha de revisores solo
  incluye personas activas de la empresa con `close.approve`, resuelta online.
- **AC-03.** Revisar exige `close.approve`, ser el revisor asignado y ser un
  sujeto distinto del preparador. Aplicacion y PostgreSQL hacen fallar cerrado
  la auto-revision y una segunda decision.
- **AC-04.** Antes de decidir, la API recalcula la manifestacion dentro del mismo
  contexto company-scoped. Si el digest cambio, responde conflicto y exige una
  version nueva; no revisa evidencia obsoleta.
- **AC-05.** `evidence_reviewed` solo es admisible si el diagnostico fijado sigue
  `ready_for_review`; un expediente bloqueado solo admite `changes_requested`.
- **AC-06.** Paquete y decision son append-only, llevan RLS forzada y no conceden
  `UPDATE`/`DELETE` al runtime. La auditoria de crear/decidir se confirma en la
  misma transaccion y no registra la manifestacion.
- **AC-07.** Replay por clave idempotente devuelve el mismo resultado; una clave
  reutilizada con otro payload conflictua y la concurrencia tiene un ganador.
- **AC-08.** API y web declaran `financial_effect=none`, `certifies_close=false`
  y `can_execute_close=false`; no existe boton ni endpoint de cierre.
- **AC-09.** Unitarias, PostgreSQL/RLS, concurrencia, web, E2E, Axe, lint, tipos,
  build, quality gate y handoff quedan reproducibles y verdes.

# Rollback

El rollback de producto retira rutas y presentacion, pero conserva el ledger
append-only ya creado. La migracion es forward-only y no habilita datos reales.
Accounting, Security, Database, Architecture, Product y QA deben revisarla de
forma independiente antes de cualquier promocion.

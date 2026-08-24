---
id: FNC-REC-002
alias: FNC-P4.7
title: Propuesta y decision humana de conciliacion sin efecto financiero
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 1c9cbf5336b5c04a3672d7eb9e2200f48143c3db
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Accounting, Security, Database, Backend/Architecture, Accessibility/QA]
---

# Resultado esperado

Un preparador puede convertir un par exacto del explorador en una propuesta de
conciliacion y un revisor diferente puede confirmarla o rechazarla. La propuesta
y la decision quedan company-scoped, auditadas e idempotentes. Confirmar registra
un juicio humano, pero no fusiona movimientos, cambia importes, acredita saldos,
alimenta cierre ni genera un informe certificado.

# Autoridad y limites

- ADR-015 y FNC-DOM-004: atributos financieros generan candidatos, nunca
  identidad dura; la decision y la evidencia se conservan append-only.
- `idempotency-dedupe.json`: par ordenado, historial append-only, reversal
  posterior y efecto financiero de confirmacion bloqueado hasta revision humana.
- RBAC/ABAC/SoD: `match.propose`, `match.confirm` y `match.reject` ya existen;
  quien propone no puede confirmar su propia propuesta.
- FNC-REC-001: el candidato se vuelve a validar server-side; la UI no es
  autoridad de elegibilidad.
- ADR-027 queda Proposed. Esta rebanada es local y sintetica y no acepta su
  semantica para produccion.

# Definition of Ready

- Base declarada integrada, CI verde y arbol limpio.
- FNC-REC-001 disponible y sin persistencia previa de candidatos.
- Integration Steward reserva migracion, API, web, pruebas y documentos.
- No se requieren datos reales, servicios externos, IA ni cambios de movil.

# Rutas permitidas

- `docs/adr/ADR-027-reconciliation-review-ledger.md` y `docs/adr/README.md`.
- `db/migrations/V0017__reconciliation_review_ledger.sql`.
- `db/tests/test_reconciliation_decisions.py`.
- `apps/api/src/fincilia_api/reconciliation.py` y `routes.py`.
- `apps/api/tests/**`.
- `apps/web/src/**` y `apps/web/tests/**`.
- `.github/workflows/ci.yml` solo si una suite nueva no queda descubierta.
- Ficha, handoff y registros centrales por Integration Steward.

# Rutas prohibidas

- Movimientos, source records, raw y evidencia originales.
- Auto-match, score probabilistico, tolerancia monetaria o conversion de moneda.
- Match groups N:M, cierre, balances certificados, reversal y exportacion.
- Workers, conectores, movil, IA, datos reales y ADR Accepted.

# Criterios de aceptacion

- **AC-01.** Crear propuesta exige `match.propose`, par elegible recalculado en
  servidor y una clave idempotente; IDs ajenos responden de forma neutral.
- **AC-02.** El par se ordena por UUID y es unico por empresa y version de regla,
  sin convertir fecha/monto/referencia en identidad de movimientos.
- **AC-03.** Repetir clave y payload devuelve el resultado original; reutilizar
  la clave con otro payload devuelve conflicto y no crea un segundo efecto.
- **AC-04.** Confirmar exige `match.confirm` y sujeto distinto del proponente;
  rechazar exige `match.reject`. La base vuelve a comprobar SoD.
- **AC-05.** Propuestas y decisiones son append-only, con RLS forzada y sin
  UPDATE/DELETE para el runtime.
- **AC-06.** La decision guarda motivo cerrado, actor, regla, evidencia de ambos
  movimientos, audit event e instante; una segunda decision terminal conflictua.
- **AC-07.** Propuesta/decision y auditoria permitida se confirman en una sola
  transaccion. Errores y logs no incluyen importes, referencias o descripciones.
- **AC-08.** Listado e historial exigen alcance server-side y muestran estado
  abierto, confirmado o rechazado sin afirmar conciliacion de saldos.
- **AC-09.** La web ofrece proponer solo a quien puede hacerlo y decidir solo a
  quien tiene permiso; nunca reconstruye SoD ni elegibilidad como autoridad.
- **AC-10.** UI y API distinguen replay, conflicto, SoD, scope, estado terminal,
  degradacion y ausencia; no convierten errores en exito.
- **AC-11.** PostgreSQL real prueba concurrencia, replay, conflicto de clave,
  cross-company, permisos, SoD, append-only, auditoria y no mutacion financiera.
- **AC-12.** Unitarias, lint, tipos, build, E2E, Axe, validadores, quality gate y
  handoff pasan; S1-READY y revisiones humanas no se mueven.

# Rollout y rollback

Solo entorno local sintetico. El rollback de aplicacion retira endpoints y UI;
la migracion es forward-only y sus filas se conservan como ledger de auditoria.
Antes de produccion Accounting debe aceptar vocabulario/efecto y Security/DB
deben revisar RLS, SoD, privilegios e idempotencia.

# Definition of Done

- AC-01..AC-12 con evidencia reproducible y commits incrementales.
- ADR-027 permanece Proposed y el efecto financiero permanece `none`.
- Rutas liberadas, handoff `REVIEW_PENDING`, CI verde sobre el head entregado.

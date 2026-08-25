---
id: FNC-REC-004
title: Exclusividad uno-a-uno de confirmaciones de conciliacion
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 94142c2
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Accounting, Security, Database, Backend/Architecture, Accessibility/QA]
---

# Resultado

Impedir que un movimiento quede confirmado simultaneamente contra dos
contrapartes. La garantia vive en PostgreSQL, resiste decisiones concurrentes y
la API/web explican el conflicto sin convertir la confirmacion en efecto
financiero, conciliacion de saldos o cierre.

# Definition of Ready

- FNC-REC-001..003 estan integradas y ADR-027 permanece Proposed.
- Base `94142c2`, arbol limpio y datos exclusivamente sinteticos.
- El ledger V0017 es append-only; una migracion nueva debe ser expand-only y no
  puede editar una migracion aplicada.

# Rutas reservadas

- `db/migrations/V0025__exclusive_confirmed_match_members.sql`.
- `db/tests/test_reconciliation_exclusivity.py`.
- `apps/api/src/fincilia_api/reconciliation.py` y pruebas relacionadas.
- `docs/database/migration-tooling.json` y la prueba adjudicada de funciones
  privilegiadas, solo para registrar la nueva guarda sin relajar la politica.
- rutas y acciones web de conciliacion y sus pruebas.
- ADR-027, ficha, handoff y registros centrales por Integration Steward.

# Criterios de aceptacion

- **AC-01.** Una confirmacion reserva exactamente sus dos movimientos en una
  proyeccion append-only company-scoped; cada movimiento tiene como maximo una
  confirmacion vigente en esta semantica terminal.
- **AC-02.** Dos confirmaciones concurrentes que comparten un movimiento tienen
  un solo ganador; la otra revierte decision, auditoria y recibo.
- **AC-03.** La garantia se aplica tambien a una insercion directa en el ledger,
  no depende de una comprobacion previa de la API.
- **AC-04.** Rechazar candidatos y proponer candidatos superpuestos sigue
  permitido; la exclusividad solo nace con `confirmed`.
- **AC-05.** RLS, FKs, privilegios minimos y triggers impiden reservas falsas,
  reescritura o borrado por el runtime.
- **AC-06.** La API devuelve un conflicto estable y audita la denegacion fuera
  de la transaccion revertida, sin filtrar valores financieros.
- **AC-07.** La web explica el conflicto y mantiene visibles ambos expedientes,
  sin afirmar conciliacion de saldos.
- **AC-08.** PostgreSQL real, API, web, tipos, lint, build, validadores y handoff
  pasan; ADR-027 y S1-READY no se promueven.

# Limites

No crea grupos N:M, asignaciones parciales, reversals, cierre, auto-match ni
efecto contable. La tabla nueva es una guarda de integridad del juicio humano,
no una fuente de saldos. No habilita datos reales, IA, movil ni produccion.

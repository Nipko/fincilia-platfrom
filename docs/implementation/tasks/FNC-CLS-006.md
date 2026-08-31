---
id: FNC-CLS-006
title: Cierre y reapertura real de periodo con snapshot inmutable
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: b2a7603
gate: S1-READY/DRG-00/DRG-01
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Accounting, Database, Security, Architecture, QA]
---

# Resultado esperado

Cerrar un periodo únicamente desde un expediente vigente y revisado, materializar
un snapshot digest-only, bloquear nuevas escrituras financieras del intervalo y
permitir una reapertura append-only con decisión de una segunda persona.

# Criterios de aceptación

1. Cierre company-scoped, idempotente, concurrente y con RLS forzada.
2. Solo el revisor asignado de un expediente `evidence_reviewed` puede cerrar.
3. El digest se recalcula bajo lock; evidencia stale falla cerrada.
4. Movimiento o statement nuevo en periodo cerrado falla en PostgreSQL.
5. Reapertura exige solicitud, motivo y decisor distinto; nunca borra historia.
6. API y web muestran estado, versión, evidencia y acciones autorizadas.
7. Auditoría no contiene importes, nombres de documentos ni manifest crudo.
8. Unitarias, PostgreSQL, E2E, Axe, lint, tipos y build pasan.

# Rutas reservadas

`db/migrations/V0046__accounting_period_close.sql`, pruebas DB, módulo/rutas API,
superficie de preparación de cierre, contratos web, ADR-035 y handoff.

# Límites

Solo sintético; no certifica estados financieros, no crea asientos, no acepta
materialidad y no supera gates ni revisión independiente.


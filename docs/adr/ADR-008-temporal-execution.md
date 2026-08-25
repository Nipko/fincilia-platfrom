# ADR-008 — Temporal y verdad de ejecución

- Status: Accepted; no Temporal initially, ratified under IMP-017
- Date: 2026-08-21
- Owners: Architecture + Platform, accountable FOUNDER-01
- Gate: S1-READY
- Plan refs: §20, §24

## Decision

- PostgreSQL: definición/autorización y estado de dominio visible.
- PostgreSQL `dispatch_pointer`, leases y workers: historial durable inicial de ejecución.
- Valkey: progreso/heartbeat efímero.
- Worker: trabajo stateless e idempotente.

La definición de un job no se duplica como verdad incompatible. Reconciliadores reparan divergencias visibles.

## Consequences

La primera etapa evita el costo y la operación de Temporal. Se reabre esta ADR si las
métricas demuestran que las esperas humanas, el historial, la escala o el costo operativo
del dispatcher propio dejan de ser aceptables. Temporal no es una dependencia prevista
por defecto para Fase 2.

## Verification

Simular caída/reanudación y comprobar que estado de dominio no depende de Valkey.

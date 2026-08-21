# ADR-008 — Temporal y verdad de ejecución

- Status: Accepted pattern; provider pending
- Date: 2026-08-21
- Owners: Architecture + Platform, UNASSIGNED
- Gate: S1-READY
- Plan refs: §20, §24

## Decision

- PostgreSQL: definición/autorización y estado de dominio visible.
- Temporal: historial durable de ejecución y espera humana.
- Valkey: progreso/heartbeat efímero.
- Cola: trabajo stateless.

La definición de un job no se duplica como verdad incompatible. Reconciliadores reparan divergencias visibles.

## Consequences

Workflows largos y auditable retries; incorpora dependencia/operación Temporal desde Fase 2.

## Verification

Simular caída/reanudación y comprobar que estado de dominio no depende de Valkey.


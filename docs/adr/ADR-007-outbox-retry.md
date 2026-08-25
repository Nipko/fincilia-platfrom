# ADR-007 — Outbox, cola y ownership de retries

- Status: Accepted; PostgreSQL dispatch/leases selected by IMP-017
- Date: 2026-08-21
- Owners: Architecture + Platform, accountable FOUNDER-01
- Gate: S1-READY
- Plan refs: §24

## Decision

- Cambio de dominio y outbox en una transacción.
- Entrega al menos una vez; consumers con inbox/idempotencia.
- La primera implementación usa `dispatch_pointer`, leases y workers sobre PostgreSQL;
  no incorpora un broker adicional sin un trigger de escala medido.
- Adaptadores clasifican retryable, fatal o requires_human y no reintentan.
- Cola posee backoff de trabajo stateless.
- Temporal posee retries de workflows/timers/espera humana.
- Circuit breaker no agrega otro retry.
- Todo job tiene presupuesto de intentos, tiempo y costo.
- Efecto externo sin idempotencia no se reintenta a ciegas.

## Consequences

Evita tormentas y efectos duplicados; exige ownership explícito y reconciliación.

## Verification

TST-OUT-001 y replay demuestran atomicidad, idempotencia y DLQ visible.

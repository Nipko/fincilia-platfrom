---
task: FNC-ARC-004
title: Eventos, transactional outbox, retry ownership y dead letters
status: review_pending
implementer: Integration Steward
base_sha: 4fbb5f1
gate: S1-READY
data_ceiling: synthetic_only
---

# Resultado esperado

Materializar ADR-007/008 como contrato ejecutable que garantice atomicidad outbox/inbox,
entrega at-least-once con efecto visible idempotente, un solo owner de retry por clase de
trabajo y DLQ visible/reproducible.

## Rutas

- `docs/architecture/EVENTS_RETRIES.md`
- `docs/architecture/events-retries.json`
- `tools/event_model/**`
- `docs/implementation/handoffs/FNC-ARC-004.md`
- Ownership, CI y archivos centrales solo por Integration Steward.

## Dependencias

- FNC-ARC-001/002, FNC-DOM-004, FNC-SEC-001/002 y FNC-PLT-001.
- ADR-007 y ADR-008 aceptan patrón; proveedores/región siguen pendientes.
- PLT-005 materializará constraints y fallos concurrentes en PostgreSQL.

## Criterios de aceptación

1. Domain change + outbox y consumer receipt + effect son atómicos.
2. Envelope versionado, company-scoped, minimizado y sin schema `latest`.
3. Inbox compara digest y bloquea replay conflictivo/cross-company.
4. Queue, workflow y dispatcher tienen ownership disjunto de retries.
5. Adapter/circuit breaker no crean retry loops.
6. Todo retry tiene budget de intentos/tiempo/timeout/deadline/costo.
7. Dead letter es visible, auditable, minimizado y replay reautoriza.
8. Efecto externo no idempotente nunca se reintenta a ciegas.
9. Valkey/workflow/queue no se convierten en verdad financiera.
10. Validador y tests negativos pasan solo con datos sintéticos.

## Fuera de alcance

- Proveedor de cola/Temporal, región y valores numéricos de policy.
- SQL/migraciones, schema registry productivo o conectores.
- Pagos, fondos, credenciales o efectos externos reales.

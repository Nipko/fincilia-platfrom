---
task: FNC-PLT-005
title: Spike auth-context, RLS, outbox/inbox and synthetic parser
status: review_pending
implementer: Integration Steward
base_sha: 8060022
gate: S1-READY
data_ceiling: synthetic_only
---

# Result expected

Materialize the accepted tenancy, security and event contracts in a disposable PostgreSQL walking skeleton. Prove the concurrency and isolation properties that cannot be guaranteed by a policy kernel or document alone.

## Routes

- `spikes/FNC-PLT-005/**`
- `docs/implementation/evidence/FNC-PLT-005/README.md`
- `docs/implementation/handoffs/FNC-PLT-005.md`
- `.github/workflows/ci.yml`
- `docs/testing/TEST_CATALOG.md`

## Dependencies

- FNC-DOM-001 tenancy invariants.
- FNC-SEC-001 authorization kernel and fail-closed rules.
- FNC-ARC-004 outbox/inbox, retries and fencing contract.
- FNC-PLT-001 stack selection evidence.

## Acceptance criteria

1. Issued authorization context is a first-class, immutable-scope record.
2. Every use revalidates company, principal, purpose, expiry, revocation, underlying grant and `authorization_version`.
3. Runtime roles cannot own or bypass company-scoped RLS tables and those tables use `FORCE RLS`.
4. Cross-company read/write and pooled-context leakage tests fail closed.
5. PostgreSQL atomically enforces one active primary accounting operator.
6. Domain publication and outbox are one transaction; injected failure rolls both back.
7. Concurrent outbox claims yield one owner and a stale ACK is fenced.
8. Inbox replay is exactly-once in visible effect and digest conflict is rejected.
9. Parser output is deterministic, lineage-bearing, engine-versioned and draft-only.
10. Docker, typecheck, dependency audit, integration tests, worker tests and repository gate pass using synthetic data only.

## Out of scope

- Product migrations, real authentication or customer data.
- Production queue provider, Temporal, connector or object storage.
- Portfolio authorization context and authoritative candidate discovery.
- Actual financial parsing, canonical publication, matching or closing.

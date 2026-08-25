---
task: FNC-PLT-005
status: REVIEW_PENDING
base_sha: 8060022
implementer: Integration Steward
data_used: synthetic_only
human_acceptance: pending
---

# Handoff FNC-PLT-005

## Delivery

- Disposable executable spike in `spikes/FNC-PLT-005/`.
- PostgreSQL bootstrap with revalidated authorization context, `FORCE RLS`, atomic operator constraint, outbox claims and inbox receipts.
- TypeScript boundary plus concurrency/integration tests.
- Python draft-only parser with deterministic manifest and origin locators.
- Reproducible evidence in `docs/implementation/evidence/FNC-PLT-005/README.md`.
- Dedicated CI job.

## Verification

```powershell
wsl -d Ubuntu -- bash -lc "cd '/mnt/c/Users/USER/Desktop/Projects/knowledge-app/spikes/FNC-PLT-005' && docker compose up -d --wait"
wsl -d Ubuntu -- bash -lc "cd '/mnt/c/Users/USER/Desktop/Projects/knowledge-app/spikes/FNC-PLT-005' && docker compose --profile test run --rm integration-test"
wsl -d Ubuntu -- bash -lc "cd '/mnt/c/Users/USER/Desktop/Projects/knowledge-app/spikes/FNC-PLT-005/worker' && python3 -m unittest -v"
```

Observed locally: 11/11 Vitest integration tests and 6/6 Python tests pass; typecheck and dependency audit pass.

## Review requested

- Architecture: transactional boundary, issued-context lifecycle and relationship to DOM-001.
- Security: `SECURITY DEFINER`, least privilege, context activation and fail-closed behavior.
- Database: partial unique index, RLS policies, claims, leases and future migration form.
- Platform: image lifecycle, secrets replacement, metrics and recovery semantics.

## Explicit follow-ups

1. V0021 materializó el contexto sin copiar el bootstrap: alcance inmutable, revocación append-only, RLS y referencias HMAC; ver FNC-SEC-004 (`028fd1b`).
2. Cada consumidor durable debe emitir desde un `TenantContext` resuelto server-side; callers nunca eligen principal ni company confiables.
3. Define portfolio-scoped authorization and authoritative company discovery independently of cached candidates.
4. Emit audit events for issue/use/revoke/failure and privileged database operations.
5. Add lease-expiry, crash-before-ACK and retry-budget scenarios when the dispatcher module is built.
6. Integrate the parser through object storage/job manifests; do not give it database write credentials.

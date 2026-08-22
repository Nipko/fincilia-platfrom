# FNC-PLT-005 — authorization, RLS and event boundary spike

This disposable spike validates the security and processing boundary with synthetic data only. It is not a production migration and must never receive customer files.

## What it proves

- An `issued_authorization_context` is revalidated against company, principal, purpose, expiry, revocation and the current `authorization_version` before any company-scoped transaction.
- The runtime roles are non-owner, non-superuser and `NOBYPASSRLS`; sensitive tables use `FORCE ROW LEVEL SECURITY`.
- A partial unique index, rather than an in-memory policy check, permits at most one active `primary_accounting_operator` per company under concurrent writes.
- A domain publication and its outbox event commit or roll back together.
- Two event workers cannot claim the same event concurrently; lease owner and `lock_version` fence stale acknowledgements.
- Inbox receipt and consumer effect are atomic. A replay with the same digest is harmless and an event ID reused with different content is rejected.
- The Python parser produces a deterministic draft with field-level origin locators and a pinned `engine_release`; it has no publication authority.

## Run in WSL

From PowerShell at the repository root:

```powershell
wsl -d Ubuntu -- bash -lc "cd '/mnt/c/Users/USER/Desktop/Projects/knowledge-app/spikes/FNC-PLT-005' && docker compose up -d --wait"
wsl -d Ubuntu -- bash -lc "cd '/mnt/c/Users/USER/Desktop/Projects/knowledge-app/spikes/FNC-PLT-005' && docker compose --profile test run --rm integration-test"
wsl -d Ubuntu -- bash -lc "cd '/mnt/c/Users/USER/Desktop/Projects/knowledge-app/spikes/FNC-PLT-005/worker' && python3 -m unittest -v"
```

Remove the disposable database afterwards:

```powershell
wsl -d Ubuntu -- bash -lc "cd '/mnt/c/Users/USER/Desktop/Projects/knowledge-app/spikes/FNC-PLT-005' && docker compose --profile test down --volumes --remove-orphans"
```

The local passwords are deliberately non-secret test markers. The database binds only to WSL loopback.

## Explicit limits

- SQL bootstrap is evidence, not the production migration strategy.
- The context ID is synthetic; authentication, token issuance and session assurance remain outside this spike.
- Security-definer functions require independent database-security review before reuse.
- The parser handles an in-memory synthetic tabular shape, not CSV/XLSX/PDF/DIAN.
- Portfolio candidate enumeration, backup/restore, delete ledger and production observability remain separate work.

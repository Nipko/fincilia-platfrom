# Evidence FNC-PLT-005

- Date: 2026-08-21
- Base: `8060022`
- Data classification: synthetic only
- Artifact: `spikes/FNC-PLT-005/`
- Technical result: PASS
- Human acceptance: pending Architecture, Security and Database review

## Reproducible result

| Evidence | Result |
|---|---:|
| Compose validation and PostgreSQL 17 health | PASS |
| TypeScript strict typecheck | PASS |
| npm dependency audit at high severity | PASS, 0 reported |
| PostgreSQL integration suite | PASS, 11/11 |
| Python parser boundary suite | PASS, 6/6 |
| Synthetic-data ceiling | PASS |

The integration suite ran in the pinned Node container against the pinned PostgreSQL image. Timings are deliberately not treated as a capacity benchmark.

## Properties observed

1. `TST-RLS-001`: a context for company one cannot insert company two and only sees company one.
2. `TST-RLS-002`: a subsequent pooled query without transaction-local context sees zero company records.
3. `TST-AUTH-001/002`: version drift, revocation, expiry and purpose mismatch reject before domain work.
4. `TST-TEN-001-N09`: two concurrent primary-operator inserts produce one success, one unique-constraint rejection and one active row.
5. `TST-OUT-001/002`: record plus outbox commit together; an injected post-outbox failure leaves neither row.
6. `TST-RET-001`: two concurrent worker claims return one event total; a repeated ACK with the old lease version is rejected.
7. `TST-INB-001/002`: identical delivery replays without a second visible effect; changed digest for the same identity is rejected.
8. `TST-DB-001`: application and event-worker roles report `rolsuper=false` and `rolbypassrls=false`; both company-scoped tables report `relforcerowsecurity=true`.
9. Parser tests prove deterministic replay, field-level origin locators, pinned engine release, tamper detection and rejection of non-synthetic or publish requests.

## Interpretation

The spike resolves two architectural gaps reported during review: atomic uniqueness for `primary_accounting_operator` belongs in PostgreSQL, and an issued authorization context must be a revalidable entity rather than an assumption carried only by a cache or session. It also executes the ARC-004 transactional and fencing contract on real PostgreSQL.

It does not approve the SQL for production. In particular, `SECURITY DEFINER` ownership, function search paths, grants, migrations, audit events and operational recovery need their own review and implementation.

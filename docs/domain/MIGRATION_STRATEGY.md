# Estrategia de migraciones v0

- Estado: Proposed
- ADR: ADR-002

SQL-first, forward-only, checksums y rol migrator separado. La aplicación runtime no genera DDL.

| Banda | Ownership |
|---|---|
| V0010–V0049 | IAM, tenancy y RLS |
| V0050–V0069 | platform, jobs y outbox |
| V0070–V0089 | ingestion, clean y lineage |
| V0090–V0109 | finance y completeness |
| V0110–V0119 | reconciliation |
| V0120–V0129 | close y reporting |
| V0130–V0139 | billing y audit index |

## Reglas

- No renumerar una migración integrada.
- Expand/contract para cambios compatibles.
- Backfill grande es job versionado, no DDL prolongado.
- Probar desde DB vacía y desde último snapshot soportado.
- Seeds únicamente sintéticos.
- Delete ledger real vive fuera de esta DB restaurable.
- Materialized projections no tienen grants directos.
- Solo un Migration Owner asigna números.


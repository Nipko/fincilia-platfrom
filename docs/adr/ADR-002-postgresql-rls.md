# ADR-002 — PostgreSQL, RLS y migraciones

- Status: Accepted; ratified by FOUNDER-01 under IMP-017
- Date: 2026-08-21
- Owners: Architecture + Security, accountable FOUNDER-01
- Gate: S1-READY
- Task: FNC-PLT-001
- Plan refs: §23.2, §29

## Decision

- PostgreSQL soportado, mínimo 17 para la primera línea de producto; el spike fijó 17.11 y cada engine release fijará patch y digest.
- SQL-first y migraciones forward-only con checksums.
- Roles migrator, owner, app y worker separados.
- Runtime nunca owner, superuser ni BYPASSRLS.
- FORCE ROW LEVEL SECURITY en tablas company-scoped.
- Company context mediante SET LOCAL dentro de cada transacción.
- FK financiera compuesta company_id + id.
- Vistas normales security_invoker; proyecciones materializadas sin grants directos.
- SECURITY DEFINER prohibido en finanzas salvo excepción auditada.
- El migrador seleccionado es el implementado por Fincilia en `db/migrate/apply.py`:
  SQL-first, checksums de contenido, orden estricto, lock de concurrencia, replay y
  PostgreSQL 17. No se adopta Flyway en esta etapa.

## Spike result

- PostgreSQL 17.11 aplicó `FORCE RLS` a grants, registros company-scoped y outbox.
- El rol runtime no fue owner, superuser ni `BYPASSRLS`.
- `pg` con pool y `set_config(..., true)` no filtró contexto después de commit/rollback.
- El grant se verificó server-side dentro de la misma transacción.

## Open implementation controls

- API final del wrapper transaccional y telemetría de contextos ausentes.
- UUIDv7 y extensiones.

FNC-DB-001 comparó Flyway, Dbmate y node-pg-migrate. FNC-DB-002 y la construcción local
ejercieron las invariantes con PostgreSQL real; el migrador propio ya es la ruta usada por
el producto local. La selección elimina una dependencia binaria adicional, pero no
elimina la revisión independiente de Database/Security ni los controles de supply chain.

## Verification

TST-RLS-001/002 pasaron en FNC-PLT-001. Siguen pendientes migración desde cero productiva, referencia cross-company con FK compuesta y revisión independiente Security/Architecture.

## Rollback

El spike es descartable. Una vez integradas migraciones, cualquier cambio usa expand/contract y ADR superseding.

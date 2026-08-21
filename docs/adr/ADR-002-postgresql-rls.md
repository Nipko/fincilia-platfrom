# ADR-002 — PostgreSQL, RLS y migraciones

- Status: Proposed
- Date: 2026-08-21
- Owners: Architecture + Security, UNASSIGNED
- Gate: S1-READY
- Task: FNC-PLT-001
- Plan refs: §23.2, §29

## Decision candidate

- PostgreSQL soportado, mínimo 15; versión exacta por spike.
- SQL-first y migraciones forward-only con checksums.
- Roles migrator, owner, app y worker separados.
- Runtime nunca owner, superuser ni BYPASSRLS.
- FORCE ROW LEVEL SECURITY en tablas company-scoped.
- Company context mediante SET LOCAL dentro de cada transacción.
- FK financiera compuesta company_id + id.
- Vistas normales security_invoker; proyecciones materializadas sin grants directos.
- SECURITY DEFINER prohibido en finanzas salvo excepción auditada.

## Open decisions

- Versión exacta.
- Herramienta de migración/query.
- Pool y wrapper transaccional.
- UUIDv7 y extensiones.

## Verification

TST-RLS-001/002, migración desde cero, falta de contexto fail-closed y referencia cross-company rechazada.

## Rollback

El spike es descartable. Una vez integradas migraciones, cualquier cambio usa expand/contract y ADR superseding.


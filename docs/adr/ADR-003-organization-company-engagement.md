# ADR-003 — Organization, company y engagement

- Status: Accepted
- Date: 2026-08-21
- Owners: Architecture + Product + Legal, accountable FOUNDER-01
- Gate: S1-READY
- Task: FNC-DOM-001
- Plan refs: §6, §14

## Decision

- Organization es contenedor administrativo.
- Company es frontera financiera permanente e independiente.
- Engagement es delegación revocable de una organización hacia una company.
- Membership y engagement no bastan: cada acción requiere grant vigente.
- Company nunca contiene firm_id.
- Cambiar de contador revoca/crea engagements sin mover el histórico.
- Authorization version invalida grants, jobs, links, schedules y cache.

## Consequences

Facilita portabilidad y evita secuestro de datos por una firma. Añade autorización explícita y manejo cuidadoso de múltiples relaciones.

## Verification

TST-TEN-001 y pruebas cross-company; revocar engagement conserva datos y elimina acceso.

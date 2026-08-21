---
id: FNC-DOM-001
title: Modelo de tenancy y cambio de firma
epic: FNC-EP-004
phase: F0
iteration: E0
type: design
status: review_pending
priority: P0
accountable_owner: UNASSIGNED
implementer: Einstein
base_sha: f621236
agent_lane: A2
independent_reviewer: Security and Accounting
plan_refs: [§6, §14, §29]
adr_refs: [ADR-003]
dependencies: [FNC-PRD-001]
gate: S1-READY
allowed_data: synthetic
file_scope: [docs/domain/TENANCY_MODEL.md, docs/implementation/handoffs/FNC-DOM-001.md, docs/adr/ADR-003-organization-company-engagement.md]
forbidden_scope: [db/migrations, apps]
---

# Resultado esperado

Congelar subject, organization, company, engagement, membership, grant y service principal sin hacer que la empresa pertenezca a una firma.

# Criterios de aceptación

- Cardinalidades e invariantes explícitas.
- Crear engagement no concede acceso implícito.
- Revocar engagement invalida grants, jobs, enlaces y caché sin mover datos.
- Máximo un primary_accounting_operator activo con capacidad de cierre.
- Responsable legal, propiedad de activo y autorización permanecen separados.
- Casos de acceso directo de la PYME y firma delegada.
- TST-TEN-001 descrito con casos positivos y negativos.

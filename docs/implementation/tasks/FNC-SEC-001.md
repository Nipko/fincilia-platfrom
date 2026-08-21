---
id: FNC-SEC-001
title: Matriz RBAC, ABAC y segregación
epic: FNC-EP-005
phase: F0
iteration: E0
type: security
status: draftable
priority: P0
accountable_owner: UNASSIGNED
agent_lane: A3
independent_reviewer: Architecture and Accounting
plan_refs: [§14, §28, §29, §54.3]
dependencies: [FNC-DOM-001, FNC-PRD-001]
gate: S1-READY
allowed_data: synthetic
file_scope: [docs/security/RBAC_ABAC_SOD.md]
forbidden_scope: [application-auth, db/policies]
---

# Resultado esperado

Definir decisiones allow/deny por subject, assurance, membership, engagement, grant, recurso, acción, finalidad y SoD.

# Criterios de aceptación

- Owner/Admin administrativo no recibe finanzas implícitamente.
- Preparador y aprobador final se separan por subject_id.
- Casos unipersonales tienen política y evidencia, no bypass silencioso.
- Revocación cubre sessions, jobs, reports, links, schedules y caches.
- Matriz positiva/negativa por rol y acción.
- IP/dispositivo son señales, no identidad.


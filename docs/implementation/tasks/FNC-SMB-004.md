---
id: FNC-SMB-004
title: Flujo pyme de tres pasos y bandeja de pendientes
epic: FNC-EP-PYME
phase: F0
iteration: E0
type: implementation
status: review_pending
priority: P1
accountable_owner: FOUNDER-01
agent_lane: A1
implementer: Claude + Integration Steward
independent_reviewer: UNASSIGNED
plan_refs: []
adr_refs:
  - ADR-039
dependencies:
  - FNC-PRD-002
gate: S1-READY
allowed_data: synthetic
security_impact: medium
privacy_impact: low
file_scope:
  - apps/web/
forbidden_scope:
  - datos financieros reales
risk_ids: []
---

# Resultado esperado

La pyme ve Subir → Revisar pendientes → Listo; el flujo de siete etapas queda como modo contador.

# Contexto y decisión que habilita

FNC-PRD-002 (pyme directa y perfiles operativos) y ADR-039.

# Criterios de aceptación

- AC-01: el alta pregunta cuántas personas revisan las finanzas y sugiere el perfil.
- AC-02: la bandeja muestra solo lo que no cuadra, con la explicación del candidato.
- AC-03: el estado del cierre muestra `autorrevisado` o `certificado` sin ambigüedad.
- AC-04: Playwright y axe cubren el flujo nuevo.

# Evidencia requerida

Pruebas sintéticas ejecutadas, handoff con comandos y resultados, y revisión independiente.

---
id: FNC-SMB-005
title: Aprobación del motor sin CLI para el usuario final
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
  - apps/api/src/fincilia_api/
  - db/
forbidden_scope:
  - datos financieros reales
risk_ids: []
---

# Resultado esperado

El usuario final nunca ejecuta una CLI para publicar un dataset; usa el release vigente aprobado por el operador de plataforma.

# Contexto y decisión que habilita

FNC-PRD-002 (pyme directa y perfiles operativos) y ADR-039.

# Criterios de aceptación

- AC-01: publicar un dataset no requiere pasos fuera de la web.
- AC-02: la aprobación de releases sigue siendo de plataforma, auditada y separada de las empresas.

# Evidencia requerida

Pruebas sintéticas ejecutadas, handoff con comandos y resultados, y revisión independiente.

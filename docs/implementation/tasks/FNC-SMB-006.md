---
id: FNC-SMB-006
title: Buzón de extractos, programación y resúmenes
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
  - workers/notification/
  - apps/web/
forbidden_scope:
  - datos financieros reales
risk_ids: []
---

# Resultado esperado

La empresa reenvía su extracto a un buzón propio o recibe un recordatorio programado, y recibe un resumen de lo conciliado y lo pendiente.

# Contexto y decisión que habilita

FNC-PRD-002 (pyme directa y perfiles operativos) y ADR-039.

# Criterios de aceptación

- AC-01: los canales externos (correo, WhatsApp) siguen apagados hasta DRG-00 y ADR-037.
- AC-02: el resumen no incluye montos ni PII en canales externos.

# Evidencia requerida

Pruebas sintéticas ejecutadas, handoff con comandos y resultados, y revisión independiente.

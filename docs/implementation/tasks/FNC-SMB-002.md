---
id: FNC-SMB-002
title: Facturas DIAN UBL, MT940 y plantillas bancarias
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
  - packages/contracts/python/fincilia_contracts/
  - workers/document/
forbidden_scope:
  - datos financieros reales
risk_ids: []
---

# Resultado esperado

El extracto bancario se lee sin mapeo manual cuando la plantilla es inequívoca, y las facturas electrónicas DIAN emitidas quedan disponibles como contraparte.

# Contexto y decisión que habilita

FNC-PRD-002 (pyme directa y perfiles operativos) y ADR-039.

# Criterios de aceptación

- AC-01: UBL `Invoice` y `AttachedDocument` se leen con montos Decimal y linaje por etiqueta; DOCTYPE/ENTITY se rechazan.
- AC-02: MT940 valida saldo inicial + movimientos = saldo final y reporta la diferencia.
- AC-03: una plantilla bancaria solo se aplica si coincide de forma única; si no, se usa el mapeo actual.
- AC-04: todos los fixtures son sintéticos y cumplen SYNTHETIC_DATA_POLICY.

# Evidencia requerida

Pruebas sintéticas ejecutadas, handoff con comandos y resultados, y revisión independiente.

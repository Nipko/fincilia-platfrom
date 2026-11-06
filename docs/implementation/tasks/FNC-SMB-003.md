---
id: FNC-SMB-003
title: Cruce con tolerancias, explicación llana y reglas aprobadas
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
security_impact: high
privacy_impact: low
file_scope:
  - db/migrations/
  - apps/api/src/fincilia_api/reconciliation.py
  - apps/api/tests/
  - db/tests/
forbidden_scope:
  - datos financieros reales
risk_ids: []
---

# Resultado esperado

Los candidatos incluyen tolerancias explícitas, NIT del pagador y referencia Bre-B con una explicación legible; una regla aprobada por una persona confirma casos idénticos con `review_mode = approved_rule`.

# Contexto y decisión que habilita

FNC-PRD-002 (pyme directa y perfiles operativos) y ADR-039.

# Criterios de aceptación

- AC-01: ninguna señal usa float; la diferencia de monto queda visible como partida a explicar.
- AC-02: una regla nace `proposed` y solo se activa con la aprobación que exige el perfil.
- AC-03: una regla activa nunca confirma fuentes `partial`, `unknown` o `unverified`.
- AC-04: cada aplicación registra regla, versión y aprobador, y es reversible.

# Evidencia requerida

Pruebas sintéticas ejecutadas, handoff con comandos y resultados, y revisión independiente.

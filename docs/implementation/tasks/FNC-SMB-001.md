---
id: FNC-SMB-001
title: Perfil operativo por empresa, modos de revisión y certificación posterior del cierre
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
  - db/migrations/V0067__company_operating_profile.sql
  - db/tests/test_operating_profile.py
  - apps/api/src/fincilia_api/
  - apps/api/tests/
forbidden_scope:
  - datos financieros reales
risk_ids: []
---

# Resultado esperado

Una pyme de una o dos personas propone, confirma y cierra sola con `review_mode = self_reviewed`; el contador certifica después. En `estricto` la SoD es idéntica a la actual.

# Contexto y decisión que habilita

FNC-PRD-002 (pyme directa y perfiles operativos) y ADR-039.

# Criterios de aceptación

- AC-01: `estricto` rechaza la autorrevisión en todas las tablas con SoD, con el mismo errcode que hoy.
- AC-02: `simple` acepta la autorrevisión y registra `self_reviewed`; actores distintos registran `independent`.
- AC-03: solo el owner cambia el perfil; cada cambio es append-only, auditado y aislado por RLS.
- AC-04: el cierre en `simple` nace `self_reviewed` y una certificación de otro usuario elegible lo vuelve `certified` sin mutar el cierre.

# Evidencia requerida

Pruebas sintéticas ejecutadas, handoff con comandos y resultados, y revisión independiente.

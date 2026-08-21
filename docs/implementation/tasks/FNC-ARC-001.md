---
id: FNC-ARC-001
title: C4 de contexto, contenedores y componentes
epic: FNC-EP-005
phase: F0
iteration: E0
type: architecture
status: review_pending
priority: P0
accountable_owner: UNASSIGNED
implementer: Integration Steward
base_sha: c7fe2eb
agent_lane: A2
independent_reviewer: Security and Platform
plan_refs: [§20–§26]
dependencies: [FNC-DOM-001]
gate: S1-READY
allowed_data: synthetic
file_scope: [docs/architecture/C4.md, docs/architecture/MODULE_BOUNDARIES.md, docs/architecture/module-boundaries.json, tools/architecture_model, docs/implementation/handoffs/FNC-ARC-001.md, .github/workflows/ci.yml]
forbidden_scope: [infra, apps, db/migrations]
---

# Resultado esperado

Representar actores, sistemas, contenedores y módulos, con fuentes autoritativas y dependencias permitidas.

# Criterios de aceptación

- Incluye planos control, financiero, evidencia, analítico y seguridad.
- Distingue Postgres, object storage, Temporal y Valkey.
- Muestra AI Gateway como único egress de IA.
- Define qué módulo escribe cada entidad y prohíbe escrituras cruzadas.
- Identifica decisiones A-01/A-02 pendientes sin inventarlas.
- Modelo ejecutable valida ownership único, referencias, ciclos, stores y fuentes autoritativas.

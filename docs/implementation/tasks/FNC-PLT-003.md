---
id: FNC-PLT-003
title: CI y quality gate inicial
epic: FNC-EP-006
phase: F0
iteration: E0
type: platform
status: review_pending
priority: P0
accountable_owner: UNASSIGNED
implementer: Integration Steward
base_sha: 6bca7ea
agent_lane: A4
independent_reviewer: Security and Architecture
plan_refs: [§20, §31, §52]
dependencies: [FNC-PLT-001, FNC-DAT-002]
gate: S1-READY
allowed_data: synthetic
file_scope: [.github/workflows/ci.yml, .github/dependabot.yml, tools/quality_gate, docs/testing/CI_QUALITY_GATE.md, docs/implementation/handoffs/FNC-PLT-003.md]
forbidden_scope: [production, deployment, cloud, customer-data, secrets, application-auth, db/migrations]
---

# Resultado esperado

Convertir las verificaciones locales en un gate de repositorio y CI reproducible, con permisos mínimos y sin publicar artefactos financieros.

# Criterios de aceptación

- Actions de terceros fijadas por SHA y workflow con `contents: read`.
- Política local detecta rutas de datos prohibidas, archivos sensibles, secretos de alta señal, TODO anónimo, acciones/imágenes sin pin y workflows peligrosos.
- Tests positivos y negativos del escáner sin dependencias externas.
- CI ejecuta corpus sintético, tests Python y verificación byte a byte.
- CI levanta PostgreSQL y ejecuta typecheck, audit, RLS/outbox y worker del spike.
- Cleanup de contenedores/volúmenes ocurre aun si falla el job.
- No se suben artifacts, logs financieros o resultados externos.

# Restricción de fase

Este gate cubre scaffolding sintético de E0. No constituye pipeline productivo ni despliegue.

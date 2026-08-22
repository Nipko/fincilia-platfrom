---
id: FNC-UX-001
title: Arquitectura de información y prototipo base
epic: FNC-EP-007
phase: F0
iteration: E0
type: design
status: review_pending
priority: P1
accountable_owner: UNASSIGNED
agent_lane: A6
independent_reviewer: Product and Accessibility
plan_refs: [§5–§13, §54.5]
dependencies: [FNC-PRD-001]
gate: S1-READY
allowed_data: synthetic
implementer: Integration Steward
base_sha: 3989ea3
file_scope: [docs/ux/INFORMATION_ARCHITECTURE.md, docs/ux/prototypes, tools/ux_contract, docs/implementation/handoffs/FNC-UX-001.md]
forbidden_scope: [apps, real-data]
---

# Resultado esperado

Prototipo navegable de Portafolio, Importación, Conciliación, Cierre y Solicitud móvil con datos sintéticos.

# Criterios de aceptación

- Original, extracción, dataset limpio y esquema canónico están diferenciados.
- El origen página/hoja/fila/columna/celda es visible.
- Estados vacío, error, degradado, parcial y ambiguo están diseñados.
- Teclado, foco, encabezados y estados no dependientes solo de color.
- Móvil se limita a captura, solicitudes y decisiones simples.
- Mapping masivo y cierre final permanecen web.
- Un validador reproducible comprueba estructura, estados, límites móvil/web y controles básicos de accesibilidad.

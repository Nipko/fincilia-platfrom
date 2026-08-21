---
id: FNC-DAT-001
title: Taxonomía y política de datos por gate
epic: FNC-EP-004
phase: F0
iteration: E0
type: design
status: review_pending
priority: P0
accountable_owner: UNASSIGNED
implementer: Bohr
base_sha: f621236
agent_lane: A5
independent_reviewer: Privacy and Accounting
plan_refs: [§7, §15, §31, §48]
dependencies: [FNC-PRD-001]
gate: S1-READY
allowed_data: synthetic
file_scope: [docs/domain/GLOSSARY.md, docs/testing/SYNTHETIC_DATA_POLICY.md, docs/implementation/handoffs/FNC-DAT-001.md]
forbidden_scope: [data, uploads, raw, customer-files]
---

# Resultado esperado

Definir fuentes, familias documentales, formatos, campos y qué datos pueden existir en cada ambiente/gate.

# Criterios de aceptación

- Distingue movimiento económico, source record y artefacto.
- Define fixtures completamente sintéticos y cómo demostrarlo.
- Prohíbe usar información anonimizada como sintética.
- Incluye locales, encodings, fechas, monedas, saldos y duplicados legítimos.
- Define sanitización y aprobación posterior a DRG-00 sin implementarla todavía.

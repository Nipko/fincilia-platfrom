---
id: FNC-PRD-001
title: PRD general y wedge inicial
epic: FNC-EP-003
phase: F0
iteration: E0
type: product
status: draftable
priority: P0
accountable_owner: UNASSIGNED
agent_lane: A1
independent_reviewer: Accounting and Architecture
plan_refs: [§1–§4, §48]
dependencies: [FNC-GOV-001]
gate: S1-READY
allowed_data: synthetic
file_scope: [docs/product/PRD_WEDGE.md]
forbidden_scope: [public-pricing, implementation]
---

# Resultado esperado

Convertir el wedge factura/pedido→pago→fee/retención→liquidación→banco→ERP en actores, problemas, flujos, alcance, exclusiones y métricas.

# Criterios de aceptación

- Comprador firma contable y PYME servida diferenciados.
- Trabajos, dolores y valor cuantificables.
- Flujo feliz, excepciones y responsabilidades web/móvil.
- Fuentes de factura emitida explícitas; buzón DIAN recibido no cubre CxC.
- No promete feed, parser universal, auto-match o acusación de fraude.
- Define hipótesis que deben validar 5 firmas y 10 cierres.


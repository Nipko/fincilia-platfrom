---
task: FNC-ARC-006
title: Paquete ejecutable de readiness de ADR bloqueantes
status: review_pending
implementer: Integration Steward
base_sha: a9741d6
integration_sha: see_git_commit_containing_this_task
gate: S1-READY
data_ceiling: synthetic_only
independent_reviewers: [Architecture, Product, Security, Accounting]
---

# Resultado esperado

Consolidar ADR-001..010 y ADR-023 en un paquete ejecutable que distinga decisiones ya
documentadas, condiciones abiertas y bloqueos humanos, sin promover por agente ningún ADR
ni declarar superado S1-READY.

## Rutas

- `docs/architecture/ADR_READINESS.md`
- `docs/architecture/adr-readiness.json`
- `tools/adr_readiness/**`
- `docs/implementation/handoffs/FNC-ARC-006.md`
- integración central por Integration Steward.

## Criterios

1. Inventario dinámico de ADR reales; el template no cuenta como decisión.
2. Cobertura obligatoria de ADR-001..010 y ADR-023.
3. Cada ADR declara alcance permitido, bloqueos, evidencia, owners y revisión.
4. `UNASSIGNED`, decisiones Proposed o condiciones abiertas impiden aceptación automática.
5. ADR-020 y decisiones posteriores se muestran sin mezclarlas con el core S1.
6. Validador fail-closed y pruebas de mutación con biblioteca estándar.

---
task: FNC-ARC-006A
title: Reconciliación cross-contract de stores, clasificación y engine release
status: review_pending
implementer: Integration Steward
base_sha: 2eb5a31
gate: S1-READY
data_ceiling: synthetic_only
independent_reviewers: [Architecture, Platform, Privacy, Security]
---

# Resultado esperado

Hacer explícita y validable la relación entre stores lógicos y físicos, entre el
vocabulario canónico y el operativo de clasificación, y entre ADR-023 y el perfil completo
de `engine_release`, sin aceptar por agente DR-ARC-001 ni DR-PRV-001.

## Rutas

- `docs/architecture/CROSS_CONTRACT_VOCABULARY.md`
- `docs/architecture/cross-contract-vocabulary.json`
- `tools/cross_contract_model/**`
- `docs/adr/ADR-023-engine-release.md`
- `docs/implementation/handoffs/FNC-ARC-006A.md`
- Integración central por Integration Steward.

## Criterios

1. Todo store de boundaries y DFD queda cubierto por un mapping explícito.
2. Stores sin flujo se declaran capacidad inactiva y no pueden persistir silenciosamente.
3. Zonas de object storage se relacionan con una capacidad lógica sin colapsar su seguridad.
4. Stores con autoridad `none` no reciben estado financiero autoritativo.
5. Clasificación canónica es subconjunto persistible; `public` y `prohibited` conservan semántica de borde.
6. El eje de dato personal permanece ortogonal, pendiente y fail-closed.
7. El perfil de release coincide exactamente con DOM-005 y ADR-023 lo referencia.
8. Validador y pruebas negativas son offline y usan solo datos sintéticos.

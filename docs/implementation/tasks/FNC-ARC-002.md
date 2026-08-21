---
task: FNC-ARC-002
title: DFD ejecutable y clasificacion por flujo
status: review_pending
implementer: Integration Steward
base_sha: 7a22ada
gate: S1-READY
data_ceiling: synthetic_only
---

# Resultado esperado

Convertir el DFD semilla en un contrato ejecutable que describa, para cada flujo relevante, actor, finalidad, frontera de confianza, clasificación, autenticación, cifrado, persistencia, retención/borrado, telemetría permitida, egress, amenazas, controles, prueba negativa y modo degradado.

## Rutas permitidas

- `docs/architecture/DFD.md`
- `docs/architecture/dfd-flows.json`
- `docs/architecture/C4.md` (solo estado/dependencia FNC-ARC-002)
- `tools/dfd_model/**`
- `docs/implementation/handoffs/FNC-ARC-002.md`
- `.github/workflows/ci.yml`
- `docs/testing/CI_QUALITY_GATE.md`
- `CURRENT_PHASE.md`
- `docs/implementation/BACKLOG_PHASE_0.md`

## Rutas prohibidas

- ADR aceptados.
- Modelo canónico, migraciones y contratos públicos.
- Código de producto y conectores.
- Fixtures financieros fuera del corpus sintético aprobado.

## Dependencias

- FNC-ARC-001: C4 y límites modulares en revisión.
- FNC-DAT-001: clasificación/glosario en revisión.
- FNC-SEC-001: kernel de autorización en revisión.

Las dependencias permiten un borrador verificable; la aceptación sigue requiriendo revisión humana de Architecture, Security y Privacy.

## Criterios de aceptación

1. Las siete zonas de confianza y los flujos F01–F13 están modelados sin proveedor cloud implícito.
2. Cada flujo cubre el checklist completo y usa solo clasificaciones canónicas.
3. Ningún dato `prohibited` puede transitar, persistirse o aparecer en logs.
4. Egress, IA, workers, exports, restore y revocación tienen invariantes fail-closed verificables.
5. Un validador determinista y pruebas negativas se ejecutan sin red ni dependencias externas.
6. CI valida conjuntamente arquitectura modular, DFD, política del repo, corpus y autorización.
7. El handoff conserva riesgos, decisiones abiertas y comandos reproducibles.

## Verificación

```powershell
python -m tools.dfd_model.validate
python -m unittest tools.dfd_model.test_validate -v
python -m tools.quality_gate.cli
```

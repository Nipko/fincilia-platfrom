---
id: FNC-QA-001
title: Ensayo sintético recepción a purga DRG-00
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: 0c11e0fe2269d915f84201cb6b13dad96432ac70
gate: DRG-00
gate_effect: evidence_only
data_ceiling: synthetic_only
independent_reviewers: [QA, Security, Privacy, Platform/SRE]
---

# Resultado

Un comando reproducible ejecuta con fixtures sintéticos el ciclo completo:
recepción, inventario, cuarentena, inspección, promoción o rechazo, derivación,
backup, tombstone, purga, restore, reaplicación y destrucción del laboratorio.

# Rutas

- `tools/drg00_drill/**` y `tests/drg00/**`.
- `docs/implementation/evidence/FNC-QA-001.json`.
- `.github/workflows/ci.yml` para precargar por digest la imagen de la sonda;
  el runtime conserva `--pull never` y `--network none`.
- Ficha, handoff y registros centrales por Integration Steward.

# Criterios de aceptación

1. Los doce casos LAB-T01..T12 producen un resultado individual.
2. PAN sintético, activo, credencial-shaped y formato sin scanner no llegan a raw.
3. Cuarentena y procesamiento no alcanzan red externa.
4. Tamper, cross-company, sesión revocada y cuenta compartida son denegados.
5. Restore no queda ready antes de reaplicar tombstones.
6. Destrucción termina con cero objetos activos, derivados, backups y scratch.
7. La evidencia es determinista, sin PII ni información financiera real.

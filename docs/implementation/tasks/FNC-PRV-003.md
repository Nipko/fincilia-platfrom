---
id: FNC-PRV-003
title: Saneamiento, borrado y reconciliación DRG-00
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 0c11e0fe2269d915f84201cb6b13dad96432ac70
gate: DRG-00
gate_effect: evidence_only
data_ceiling: synthetic_only
independent_reviewers: [Privacy, Legal, Security, Platform/SRE]
---

# Resultado

Un runbook ejecutable purga cuarentena, evidencia, derivados, scratch y backups,
conserva el delete ledger por la política adjudicada y reaplica tombstones antes
de declarar sano un restore.

# Rutas

- `docs/privacy/drg00-disposal-contract.json` y
  `docs/privacy/DRG00_DISPOSAL_RUNBOOK.md`.
- `tools/data_disposal/**`.
- Ficha, handoff, evidencia y registros centrales por Integration Steward.

# Criterios de aceptación

1. Un borrado sin política L-01 efectiva falla cerrado.
2. El tombstone se escribe antes de eliminar cualquier copia.
3. Toda copia conocida termina purgada o genera un blocker explícito.
4. Restore reaplica tombstones antes de readiness.
5. Los recibos contienen digests y estados, nunca valores del artefacto.
6. Reintentar es idempotente y una copia reintroducida vuelve a purgarse.

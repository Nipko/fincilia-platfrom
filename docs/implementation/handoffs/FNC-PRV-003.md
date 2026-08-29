---
task: FNC-PRV-003
status: REVIEW_PENDING
base_sha: 0c11e0fe2269d915f84201cb6b13dad96432ac70
implementation_sha: fe58e8f
data_ceiling: synthetic_only
---

# Handoff FNC-PRV-003

La purga valida política efectiva y exige que el delete ledger sobreviva al
backup. Hace fsync del tombstone antes del primer unlink, registra la transición,
elimina toda copia inventariada y reconcilia. Reintentar es idempotente.

Restore permanece sin readiness hasta cargar el delete ledger separado,
reaplicar tombstones —incluidos digests derivados históricos— y reconciliar.
Los recibos son metadata y digests, nunca contenido.

Verificación: `python3 -m unittest tools.data_disposal.test_service -v` — 4
pruebas. L-01 continúa pendiente de Legal/Privacy/Accounting; solo se ejercitó
`SYNTHETIC-TEST-POLICY`. Revisión independiente: Privacy, Legal, Security y
Platform/SRE.

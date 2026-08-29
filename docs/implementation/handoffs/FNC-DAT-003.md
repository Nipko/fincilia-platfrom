---
task: FNC-DAT-003
status: REVIEW_PENDING
base_sha: 0c11e0fe2269d915f84201cb6b13dad96432ac70
implementation_sha: 69d6aba
data_ceiling: synthetic_only
---

# Handoff FNC-DAT-003

Se implementó un inventario NDJSON append-only con cadena SHA-256, secuencia,
operación idempotente, transiciones cerradas y reconciliación con todas las
zonas. Las referencias son opacas; no existe campo para nombre, correo, empresa
legible, cuenta, monto o contenido.

Una prueba adversarial encontró que una referencia retirada se validaba después
de escribir. La validación ahora reconstruye el candidato completo antes de
abrir el descriptor.

Verificación: `python3 -m unittest tools.corpus_inventory.test_ledger -v` — 5
pruebas. Rollback: retirar herramienta y contratos; ningún inventario real fue
creado. Revisión independiente: Data, Privacy, Security y QA.

---
id: FNC-DAT-003
title: Inventario nominal y append-only de artefactos DRG-00
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 0c11e0fe2269d915f84201cb6b13dad96432ac70
gate: DRG-00
gate_effect: evidence_only
data_ceiling: synthetic_only
independent_reviewers: [Data, Privacy, Security, QA]
---

# Resultado

Cada artefacto recibido por el laboratorio tiene un identificador opaco, digest,
finalidad, sujeto de retención, estado y cadena de eventos verificable. El
inventario nunca conserva nombre de fichero, contenido, correo ni identificador
financiero.

# Rutas

- `docs/security/drg00-corpus-inventory.json` y documentación.
- `tools/corpus_inventory/**`.
- Ficha, handoff, evidencia y registros centrales por Integration Steward.

# Criterios de aceptación

1. Alta, promoción, rechazo, derivación, tombstone y purga son append-only.
2. Cada evento encadena el digest del evento anterior y detecta tamper.
3. Estados y transiciones inválidas fallan cerrados.
4. Ningún artefacto activo desaparece sin tombstone y recibo de purga.
5. El inventario se reconcilia con todas las zonas del laboratorio.
6. La salida es metadata allowlisted y no replica payload.

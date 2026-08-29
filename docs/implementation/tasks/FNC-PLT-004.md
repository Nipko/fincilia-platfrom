---
id: FNC-PLT-004
title: Ambiente aislado reproducible para corpus DRG-00
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 0c11e0fe2269d915f84201cb6b13dad96432ac70
gate: DRG-00
gate_effect: evidence_only
data_ceiling: synthetic_only
independent_reviewers: [Security, Privacy, Architecture, Platform/SRE]
---

# Resultado

Materializar el diseño FNC-SEC-003 como un laboratorio efímero, sin red externa,
con zonas de cuarentena, evidencia, derivados, archivo, borrado y scratch
separadas. El entorno ejecuta únicamente fixtures sintéticos hasta la
consolidación humana de DRG-00.

# Rutas

- `infra/drg00-lab/**`.
- `docs/security/drg00-lab-runtime.json` y guía operativa.
- `tools/drg00_lab/**`.
- Ficha, handoff, evidencia y registros centrales por Integration Steward.

# Criterios de aceptación

1. Ningún proceso del laboratorio dispone de red o puerto publicado.
2. El filesystem raíz del ejecutor es read-only, no-root y sin privilegios.
3. Las zonas persistentes y efímeras son explícitas y no se mezclan.
4. Intake exige manifiesto aprobado y deposita primero en cuarentena.
5. El controlador falla cerrado si faltan scanner, inventario, política o gate.
6. `destroy` reconcilia inventario, derivados, backups y scratch.
7. Unitarias, prueba Docker sintética y contrato pasan.

# Límites

No habilita datos reales, no selecciona A-02/L-01, no activa IdP y no acepta
revisiones humanas. La evidencia técnica reduce bloqueos; no firma DRG-00.

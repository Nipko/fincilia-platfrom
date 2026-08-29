---
task: FNC-PLT-004
status: REVIEW_PENDING
base_sha: 0c11e0fe2269d915f84201cb6b13dad96432ac70
implementation_sha: 0a58196
data_ceiling: synthetic_only
---

# Handoff FNC-PLT-004

Se materializó un laboratorio efímero con zonas separadas y dos sondas Docker
sin red. Ambas comprobaron UID 65532, root read-only, tmpfs acotado, cero DNS y
cero TCP externo. Compose no publica puertos, no monta el host, no usa
privilegios y no descarga imágenes durante el ensayo.

Rutas: `infra/drg00-lab/**`, `tools/drg00_lab/**` y contrato/runtime en
`docs/security`. Rollback: retirar el compose, herramienta y contrato; no hay
migración, volumen persistente ni recurso cloud.

Verificación: `PYTHONPATH=packages/contracts/python python3 -m unittest
tools.drg00_lab.test_lab -v` y `python3 -m tools.drg00_lab.runtime`.

Límites: la release productiva sigue sin admitirse hasta firma/procedencia. El
runtime acepta solo la política sintética del ensayo y no autoriza datos reales.
Revisión independiente: Security, Privacy, Architecture y Platform/SRE.

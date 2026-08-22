---
id: FNC-PRV-001
title: Mapa de privacidad, tratamiento, retención y borrado ejecutable
epic: FNC-EP-005
phase: F0
iteration: E0
type: privacy
status: review_pending
priority: P0
accountable_owner: UNASSIGNED
implementer: Claude (external agent) + Integration Steward
base_sha: 00d9408
integration_sha: 96c40d3
agent_lane: A4
independent_reviewers: [Legal, Security, Architecture, Product]
dependencies: [FNC-DOM-001, FNC-SEC-001, FNC-SEC-002, FNC-ARC-002, FNC-DAT-001]
gate: S1-READY
allowed_data: synthetic
file_scope:
  - docs/privacy/README.md
  - docs/privacy/PRIVACY_MAP.md
  - docs/privacy/privacy-map.json
  - tools/privacy_model/__init__.py
  - tools/privacy_model/validate.py
  - tools/privacy_model/test_validate.py
  - docs/implementation/tasks/FNC-PRV-001.md
  - docs/implementation/handoffs/FNC-PRV-001.md
forbidden_scope:
  - AGENTS.md
  - CURRENT_PHASE.md
  - docs/domain
  - docs/security
  - docs/architecture
  - docs/adr
  - backlogs
  - ownership
  - ci
  - compose
  - apps
  - workers
  - packages
  - migrations
  - lockfiles
  - root-files
---

# Resultado esperado

Un contrato de privacidad completo y **ejecutable** antes de escribir código productivo:
documentación revisable, modelo JSON validable, validador determinista y pruebas
negativas que impidan debilitar el contrato en silencio.

El mapa declara posturas provisionales y decisiones pendientes. **No acepta** decisiones
legales, riesgos residuales, regiones, proveedores ni gates en nombre de propietarios
humanos.

# Dependencias preservadas, no resueltas

| ID | Origen | Owner |
|---|---|---|
| `UD-PRIMARY-OPERATOR` | Atomicidad de `primary_accounting_operator` requiere constraint en base de datos; una comprobación en memoria no es garantía. | Architecture |
| `UD-ISSUED-CONTEXT` | Falta la entidad canónica `issued_authorization_context` con `authorization_version`, company scope, purpose, principal, `issued_at` y `expires_at`. | Architecture |
| `UD-PORTFOLIO-CANDIDATES` | La lista de companies candidatas del portafolio debe provenir de almacenamiento autoritativo. | Backend |

Tenancy, autorización y migraciones están fuera del scope: estas tres se registran como
decisiones abiertas con owner y gate.

# Datos autorizados

`synthetic_only`. No se recibieron, copiaron, procesaron ni simularon documentos reales.
Ningún correo, NIT, cuenta, token, persona o empresa real aparece en los artefactos.

# Criterios de aceptación

- `PRIVACY_MAP.md` coherente con `dfd-flows.json` y `threat-model.json`.
- `privacy-map.json` pasa `python -m tools.privacy_model.validate`.
- Cobertura de `F01`–`F13`, de todos los stores del DFD y de todas las políticas de retención usadas por el DFD.
- Cobertura de los riesgos `TM-005`, `TM-010`, `TM-011`, `TM-012` y `TM-014`.
- Roles de tratamiento expresados como matriz por actividad, no como afirmación global.
- Persona jurídica y persona natural tratadas como regímenes distintos.
- Sin región, base legal, plazo numérico ni proveedor inventado.
- IA externa deshabilitada, global y por actividad.
- Delete ledger fuera del restore ordinario; restore reaplica tombstones antes de reabrir.
- Máquina de estados de borrado completa y sin atajo `requested → completed`.
- Portabilidad y cambio de firma cubiertos; la company conserva identidad e histórico.
- Portafolio multiempresa con enumeración autoritativa y autorización empresa por empresa.
- Mínimo 18 pruebas; todas pasan.
- Ningún gate marcado como superado.

# Comandos de verificación

```bash
python -m tools.privacy_model.validate
python -m unittest tools.privacy_model.test_validate -v
python -m unittest discover -s tools/privacy_model -p "test_*.py"
```

# Revisores

| Rol | Qué debe revisar |
|---|---|
| Privacy | Owner. Inventario, minimización, derechos y borrado. |
| Legal | Owner. Roles responsable/encargado, bases jurídicas, retención, transmisión y plazos de incidente. |
| Security | Stores, logs, soporte/break-glass, delete ledger y restore. |
| Architecture | Región, dependencias abiertas y coherencia con C4/DFD. |
| Product | Analítica operativa, notificaciones y métricas de productividad. |

# Estado

`review_pending`. No supera S1-READY ni DRG-00.

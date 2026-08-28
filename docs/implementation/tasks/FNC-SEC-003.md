---
id: FNC-SEC-003
title: Diseño ejecutable del laboratorio aislado para corpus real
epic: FNC-EP-002
phase: F0
iteration: E1
type: security_readiness
status: review_pending
priority: P0
accountable_owner: FOUNDER-01
agent_lane: Security/Platform
implementer: Codex principal dev + Integration Steward
independent_reviewer: Security + Privacy + Architecture
dependencies: [FNC-SEC-002, FNC-PRV-002, FNC-ARC-003]
gate: S-01
gate_effect: none
allowed_data: synthetic_only
security_impact: critical
privacy_impact: high
risk_ids: [TM-005, TM-014, TM-015]
---

# Resultado esperado

Un contrato proveedor-neutral define el laboratorio aislado que FNC-PLT-004
deberá desplegar y probar antes del primer corpus real: identidades individuales,
MFA/step-up, privilegio JIT, cuarentena sin salida, workloads efímeros, stores
separados, auditoría inmutable y egress deny-by-default.

# Base y modalidad

- Base: `3d37b7e` en `main`; Integration Steward es el único ejecutor Git.
- Fuentes: threat model, privacy-map, A-02 y matriz L-01 ligados por digest.
- Datos: sólo configuración declarativa y fixtures sintéticos.
- A-02, L-01 y proveedor/IdP siguen pendientes; el diseño no los decide.

# Dentro de alcance

- Modelo ejecutable de zonas, identidad, red, cómputo, stores y operación.
- Cobertura dinámica de amenazas que apuntan a DRG-00.
- Prerrequisitos fail-closed y casos de aceptación para PLT-004/QA-001.
- Prohibición explícita de endpoints, región, proveedor y datos reales actuales.
- CLI validate/report, mutaciones, guía y solicitud de revisión S-01.
- Handoff y registros centrales por Integration Steward.

# Fuera de alcance

- Desplegar cloud/VPC, abrir firewall, crear cuentas, KMS, IdP o secretos.
- Seleccionar proveedor/región, aceptar riesgo o firmar S-01/DRG-00.
- Modificar threat model, privacy-map, A-02, L-01, Compose o producto.
- Ingresar un archivo, identificador, correo o dato financiero real.

# Rutas permitidas

- `docs/security/isolated-real-data-lab.json`
- `docs/security/ISOLATED_REAL_DATA_LAB.md`
- `tools/isolated_lab/**`
- ficha, handoff y solicitud S-01 de esta tarea.
- registros centrales por Integration Steward.

# Rutas prohibidas

- Infraestructura, CI, migraciones, producto, locks y ADR aceptados.
- Fuentes ligadas por digest y cualquier dato real.

# Criterios de aceptación

- **AC-01.** Fuentes y amenazas DRG-00 se descubren dinámicamente y no pueden
  quedar stale o sin control.
- **AC-02.** Quarantine no tiene egress; ningún workload tiene public IP,
  credencial larga, host mount o instalación dinámica.
- **AC-03.** Acceso humano es nominal, MFA resistente a phishing, mínimo, JIT,
  auditable y con break-glass de doble control.
- **AC-04.** Raw, derivados, auditoría/delete ledger y backups tienen límites y
  claves separadas; restore reaplica tombstones antes de reabrir.
- **AC-05.** Logs son allowlist y no reciben payload, montos, identificadores,
  nombres de archivo, tokens ni contenido documental.
- **AC-06.** Todos los prerequisitos humanos/externos están `not_met`; proveedor,
  región, endpoints y despliegue quedan nulos/deshabilitados.
- **AC-07.** El plan de pruebas incluye denegaciones, aislamiento, egress,
  cuarentena, restore, destrucción y evidencia; ninguna se declara pasada.
- **AC-08.** Unitarias, quality gate, grafo y handoff reproducible pasan.

# Handoff

Security y Privacy revisan el diseño; Architecture valida límites. PLT-004 lo
materializa sólo después de A-02/L-01 y QA-001 demuestra los controles. Ninguna
entrega técnica aislada autoriza DRG-00.

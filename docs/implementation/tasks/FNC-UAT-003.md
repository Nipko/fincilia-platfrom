---
id: FNC-UAT-003
title: Evidencia verificable del borde HTTPS UAT
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: 02c0ffc
gate: UAT
gate_effect: evidence_only
data_ceiling: synthetic_only
independent_reviewers: [Security, Platform/SRE, QA]
---

# Resultado

Una sonda de solo lectura demuestra sobre `fincilia.com` la redirección a HTTPS,
validación TLS y cabeceras defensivas de las superficies públicas de UAT sin
enviar cookies, autorización, query strings ni cuerpo.

# Rutas reservadas

- `tools/uat_edge_probe/**`.
- `docs/platform/UAT_EDGE_SECURITY.md`.
- evidencia, handoff y registros centrales por Integration Steward.

# Criterios de aceptación

1. HTTP redirige exactamente al origen HTTPS y TLS valida nombre/cadena.
2. Las diez rutas públicas esperadas responden sin redirección inesperada.
3. HSTS, CSP, anti-framing, nosniff, referrer, permissions y no-store se
   verifican por valores o invariantes exactas.
4. La sonda usa solo `HEAD` y no transmite ni conserva payload o identidad.
5. La evidencia queda ligada al commit, código de sonda y digest canónico.
6. Mutaciones de transporte, rutas, cabeceras, privacidad o revisión muerden.

# Fuera de alcance

Modificar DNS, certificado, proxy, WAF o runtime; pentest; escaneo de puertos;
datos reales; aprobación de DRG-00/01 o revisión humana independiente.

# Evidencia integrada

- Implementación: `26e8182f145782815662655d3e51839f1b4c324c`.
- Integración probada: `57c4d530fdb65000e020bb84546a0e73ff91d96a`, CI
  `33698034556` verde.
- Sonda live: 13/13 controles y 10/10 rutas públicas, 2026-09-03 UTC.
- `docs/implementation/evidence/FNC-UAT-003.json`.
- Security, Platform/SRE y QA continúan pendientes como revisores independientes.

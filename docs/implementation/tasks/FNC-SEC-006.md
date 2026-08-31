---
id: FNC-SEC-006
title: Endurecimiento HTTP verificable para UAT
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: ba91e70
implementation_sha: b44c115
tested_sha: 2bc936a
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Security, Architecture, QA]
---

# Resultado

Aplicar y verificar cabeceras defensivas coherentes en API y web sin romper
OAuth, desarrollo local ni terminación TLS en el borde.

# Rutas reservadas

- middleware y pruebas HTTP en `apps/api/**`.
- configuración y pruebas de cabeceras en `apps/web/**`.
- esta ficha, handoff y registros centrales por Integration Steward.

# Criterios de aceptación

1. La API emite `no-store`, `nosniff`, `DENY`, `no-referrer` y una política de
   permisos cerrada incluso en errores controlados.
2. La web extiende su baseline sin permitir `unsafe-eval` ni romper Google OAuth.
3. HSTS no se finge desde un runtime HTTP local ni duplica autoridad del borde.
4. Las pruebas HTTP y E2E comprueban presencia y valores exactos.
5. No se registra payload, token, identidad ni información financiera.

# Fuera de alcance

WAF, rate limit global por IP, TLS del edge y aceptación de riesgo residual; esos
cambios necesitan su propio contrato operativo y evidencia del proxy real.

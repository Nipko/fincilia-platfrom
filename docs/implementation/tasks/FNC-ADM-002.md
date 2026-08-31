---
id: FNC-ADM-002
title: Diagnóstico operativo agregado del plano de control
status: ready
implementer: Codex principal dev + Integration Steward
base_sha: ba91e70
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Security, Database/Architecture, Platform/SRE, Privacy]
---

# Resultado

Dar al superadmin métricas operativas agregadas para diagnosticar colas, fallos,
cuarentena, notificaciones y suscripciones sin conceder acceso a datos de empresa
ni devolver nombres, identificadores, importes, documentos o payloads.

# Rutas reservadas

- `db/migrations/V0052__platform_operational_diagnostics.sql`.
- pruebas PostgreSQL de administración de plataforma.
- API, web y pruebas de `/platform/diagnostics` y `/plataforma`.
- esta ficha, handoff y registros centrales por Integration Steward.

# Criterios de aceptación

1. Una función `SECURITY DEFINER` verifica rol de plataforma dentro de PostgreSQL.
2. Solo devuelve conteos y estados operativos allowlisted; nunca filas ni valores.
3. `PUBLIC` y roles sin control plane no pueden ejecutarla.
4. La API conserva autorización server-side y no acepta empresa del cliente.
5. La consola diferencia cero, indisponible y degradado.
6. ACL, RLS negativa, contrato API, UI y regresión pasan.

# Fuera de alcance

Break-glass, inspección de documentos, acceso financiero transversal, edición de
usuarios, soporte dentro de una empresa y métricas con cardinalidad sensible.

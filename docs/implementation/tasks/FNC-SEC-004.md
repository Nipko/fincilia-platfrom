---
id: FNC-SEC-004
title: Contexto de autorizacion persistente y revocable
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 9ae4e1d
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Security, Database/Architecture]
---

# Resultado

Convertir la evidencia descartable de FNC-PLT-005 y la decision aprobada
`UD-ISSUED-CONTEXT` en una capacidad productiva para jobs, exports, enlaces y
schedules que sobreviven una peticion.

# Alcance

- V0021 forward-only, RLS forzada y privilegios append-only.
- Kernel API de emision idempotente, revalidacion online y revocacion por tombstone.
- Huellas HMAC company-scoped; ninguna referencia de recurso en claro.
- Pruebas PostgreSQL positivas, negativas y cross-company.
- Sin endpoint ni pantalla artificial hasta que exista un consumidor de larga vida.

# Criterios

- Company, subject, firm, engagement, purpose y version son inmutables.
- Cada uso revalida sujeto, membresia, engagement, grant, version, expiracion y revocacion.
- Cambiar `authorization_version` invalida contextos ya emitidos.
- Runtime no puede actualizar ni borrar emisiones o revocaciones.
- Repetir una emision identica devuelve el mismo contexto; reutilizar la clave con
  otra semantica falla cerrado.
- Emision, uso y revocacion dejan auditoria sin payload ni referencia original.

# Limites

Solo datos sinteticos. No autoriza DRG-00/01, produccion, enlaces publicos ni
trabajo programado. Security y Database/Architecture deben revisar de forma
independiente antes de declarar la tarea Done.

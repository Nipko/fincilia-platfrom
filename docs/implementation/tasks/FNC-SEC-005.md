---
id: FNC-SEC-005
title: Trabajos durables vinculados a autorizacion emitida
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: b506e93
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Security, Database/Architecture]
---

# Resultado

Hacer que cada trabajo nuevo de documentos conserve el contexto persistente que
autorizo su creacion y que el protocolo de despacho lo revalide al reclamar,
escribir un lote y terminar.

# Alcance reservado

- `db/migrations/V0022__processing_run_authorization_context.sql`.
- Productor de subida en `apps/api/src/fincilia_api` y configuracion tipada.
- Consumidor en `workers/document/src/fincilia_worker`.
- Pruebas API, worker y PostgreSQL del flujo.
- Contratos de configuracion, migraciones, fase, trazabilidad y handoff.

# Criterios

- Los trabajos nuevos creados por la API llevan `issued_context_id` no nulo.
- Repetir una entrega conserva idempotencia y no emite trabajo duplicado.
- Expiracion, revocacion, cambio de version o autoridad inactiva impiden reclamar,
  sostener o completar el trabajo.
- Los trabajos anteriores a V0022 siguen siendo legibles durante el despliegue
  expand-only; el endurecimiento `NOT NULL` queda para una migracion posterior a
  demostrar que no quedan productores antiguos.
- El worker no recibe la clave HMAC y no obtiene escritura directa sobre la cola.
- Ningun payload, referencia original o secreto aparece en cola, auditoria o logs.

# Limites

Solo datos sinteticos. No supera S1-READY ni DRG-00/01. Las funciones privilegiadas
continuan sujetas a revision humana independiente de Security y Database/Architecture.

# Implementacion

Productor, consumidor, V0022 y pruebas: `c9b3094`. La migracion fue aplicada
sobre una base local que ya estaba en V0021 y el replay conserva checksums.

# Threat model v0

- Estado: Seed; requiere FNC-ARC-002 y FNC-SEC-002
- Método inicial: STRIDE + abuso de negocio

## Activos críticos

- Evidencia original y hashes.
- Datos financieros canónicos y saldos.
- Grants, engagements y sesiones.
- Decisiones de conciliación/cierre.
- Claves, secretos y enlaces de descarga.
- Audit chain, delete ledger y backups.
- Contratos, engine releases y modelos.

## Riesgos iniciales

| ID | Amenaza | Impacto | Control/prueba |
|---|---|---:|---|
| THR-001 | Lectura cross-company | Crítico | RLS/FK/scopes; TST-RLS-001 |
| THR-002 | Contexto de pool filtrado | Crítico | SET LOCAL wrapper; TST-RLS-002 |
| THR-003 | Archivo malicioso/polyglot | Alto | Quarantine, allowlist, límites, AV |
| THR-004 | Dedupe elimina pago legítimo | Crítico | Candidate no unique; TST-DED-001 |
| THR-005 | Dataset parcial llega a cierre | Crítico | Completeness gate; TST-CMP-001 |
| THR-006 | Replay duplica datos/costo | Alto | Idempotency/outbox/inbox |
| THR-007 | Worker accede a otra empresa | Crítico | Capability exacta y prueba negativa |
| THR-008 | Export/link sobrevive revocación | Alto | Revalidación y authorization_version |
| THR-009 | PAN entra al sistema | Alto | Streaming/aislamiento y QSA S-01 |
| THR-010 | Egress IA filtra datos | Crítico | AI Gateway, redacción fail-closed |
| THR-011 | Restore resucita borrados | Crítico | Delete ledger externo y tombstones |
| THR-012 | Agente sigue instrucciones de documento | Alto | Contenido no confiable, no tool execution |

Cada amenaza alta/crítica debe adquirir owner, mitigación, prueba, evidencia y riesgo residual antes de S1-READY o DRG correspondiente.


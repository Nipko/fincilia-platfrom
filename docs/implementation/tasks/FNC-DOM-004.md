---
task: FNC-DOM-004
title: Evidencia, deduplicación e idempotencia segura
status: review_pending
implementer: Integration Steward
base_sha: 96c40d3
gate: S1-READY
data_ceiling: synthetic_only
---

# Resultado esperado

Separar las identidades de entrega, artefacto, observación, evento económico y efecto
publicado. Definir idempotencia atómica y dedupe revisable sin colapsar transacciones
legítimas por similitud de fecha, monto, dirección o referencia.

## Rutas

- `docs/domain/EVIDENCE_DEDUPE_IDEMPOTENCY.md`
- `docs/domain/idempotency-dedupe.json`
- `tools/idempotency_model/**`
- `docs/implementation/handoffs/FNC-DOM-004.md`
- Ownership arquitectónico, CI y archivos centrales solo por Integration Steward.

## Dependencias

- FNC-DOM-002, FNC-ARC-002, FNC-SEC-002 y FNC-PLT-001.
- DOM-005 completa linaje granular, overlays y engine release.
- Accounting y Architecture deben definir supersession antes de un efecto productivo.

## Criterios de aceptación

1. Redelivery exacta es idempotente dentro de company/source sin perder evidencia.
2. ID de entrega no se confunde con ID de observación o de movimiento económico.
3. Misma clave con payload distinto produce conflicto y cero segundo efecto.
4. Fecha/monto/dirección/referencia/fingerprint nunca forman unicidad financiera.
5. Dos movimientos legítimos idénticos siguen siendo representables.
6. Dedupe conserva evidencia, historial y reversión append-only.
7. Constraint/transacción/outbox/fencing protegen concurrencia; Valkey no da corrección.
8. Un solo workflow durable es owner de retries.
9. Modelo, pruebas, CI y quality gate pasan con datos exclusivamente sintéticos.

## Fuera de alcance

- Migraciones SQL y constraints productivos.
- Contratos reales de IDs de bancos/proveedores.
- Merge, void o supersession automático de movimientos.
- Auto-dedupe o umbrales estadísticos.
- Conectores o payloads reales.

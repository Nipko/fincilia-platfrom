---
task: FNC-ARC-004
status: REVIEW_PENDING
base_sha: 4fbb5f1
implementer: Integration Steward
data_used: synthetic_only
human_acceptance: pending
---

# Handoff FNC-ARC-004

## Entrega

- Doce principios ejecutables para eventos, retry y fuentes de verdad.
- Envelope inmutable con aggregate version, company/purpose/schema y payload digest.
- Outbox de cinco estados, claim atómico/fencing, ack y reconciliación.
- Inbox de seis estados con receipt+effect atómicos y conflicto por digest.
- Delivery attempts append-only con cinco clases de fallo.
- Cinco clases de trabajo con owner exclusivo de calendario.
- Retry policy con límites de intentos, tiempo, timeout, deadline y costo.
- Dead-letter visible, minimizado, reautorizado y append-only al replay.
- Compatibilidad de schemas, gaps por agregado y prohibición de `latest`.
- Separación PostgreSQL/workflow/queue/Valkey/analytics.
- Controles de efecto externo, autorización/revocación y observabilidad.
- Veinte escenarios requeridos y 47 pruebas de mutación.
- `dead_letter_item` incorporado al ownership conceptual de Platform.

## Verificación

```powershell
python -m tools.event_model.validate
python -m unittest tools.event_model.test_validate -v
python -m tools.architecture_model.validate
python -m tools.idempotency_model.validate
python -m tools.dfd_model.validate
python -m tools.threat_model.validate
python -m tools.quality_gate.cli
```

Resultado previo a integración:

- Modelo ARC-004: PASS, 0 errores.
- Suite específica: 47/47 PASS.
- Ownership arquitectónico: PASS.
- Alineación DOM-004, DFD T12/C-IDEMP y TM-009: PASS.
- Solo contratos/fixtures sintéticos; no se usó red, IA o proveedor.

## Decisiones preservadas

- Evento comunica un hecho comprometido; no completa invariantes distribuidas.
- Transport at-least-once; efecto visible idempotente/effectively-once.
- No existe global order; aggregate version detecta stale/gap.
- Producer usa port de Platform dentro de la transacción, no repositorio ajeno.
- Outbox no se elimina al recibir ack; L-01 sigue pendiente.
- Queue reintenta stateless; workflow durable, timers/esperas; adapter no reintenta.
- Circuit breaker no agenda.
- Retry-after nunca supera budget/deadline.
- DLQ no contiene payload raw ni tiene autoridad financiera.
- Replay conserva idempotency key, reautoriza y crea nuevo attempt.
- Resultado externo desconocido se reconcilia antes de retry.
- Sin idempotencia externa verificada se requiere humano.
- Valkey solo progreso; workflow solo historia de ejecución.

## Revisiones requeridas

- **Architecture/Platform:** ownership, ports transaccionales, reconciliation y operación.
- **Database:** constraints, SKIP LOCKED/CAS, fencing, aislamiento y retention.
- **Security:** replay, minimización, auth version, DLQ y service principals.
- **Integrations:** clasificación estable de errores e idempotencia por proveedor.
- **Product/Accounting:** qué efectos externos/financieros exigen aprobación humana.

## Pendientes

- Elegir cola/workflow y región en A-02; no se infirió proveedor.
- Fijar policies numéricas por job con owner/revisor y COGS medido.
- PLT-005 debe inyectar crash antes/después de cada commit/ack y claims concurrentes.
- ARC-005 debe aplicar el contrato a conectores y fallback archivo.
- L-01 define retención de outbox, inbox, attempt y dead letter.

## Rollback

Retirar documento/modelo/tooling/pasos CI, quitar `dead_letter_item` de ownership y
restaurar el estado central. No hay migraciones, proveedores o efectos reales.

Esta entrega no supera S1-READY ni autoriza datos reales, pagos o producción.

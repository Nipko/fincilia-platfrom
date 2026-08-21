---
task: FNC-DOM-004
status: REVIEW_PENDING
base_sha: 96c40d3
implementer: Integration Steward
data_used: synthetic_only
human_acceptance: pending
---

# Handoff FNC-DOM-004

## Entrega

- Cinco capas de identidad separadas: entrega, bytes, observación, evento económico y efecto.
- Cinco claves duras permitidas con scope y semántica de conflicto explícitos.
- Contrato de ID de proveedor `unverified → verified → suspended`, fail-closed.
- Tres tipos de candidato que nunca crean unicidad o mutación automática.
- Lista ejecutable de cuatro unicidades financieras prohibidas.
- Fingerprints versionados/HMAC para ranking; nunca identidad ni anonimización.
- Inbox con claim atómico, terminales claros, retry owner único y fencing token.
- Dedupe económico append-only, reversible y sin borrado físico de evidencia/movimientos.
- Transactional outbox y consumidor idempotente para efecto visible exactly-once.
- Doce escenarios de aceptación y 33 pruebas positivas/negativas del contrato.
- Ownership de `dedupe_candidate` y `dedupe_decision` asignado a Finance.

## Verificación

```powershell
python -m tools.idempotency_model.validate
python -m unittest tools.idempotency_model.test_validate -v
python -m tools.architecture_model.validate
python -m tools.canonical_model.validate
python -m tools.dfd_model.validate
python -m tools.quality_gate.cli
```

Resultado antes de integrar:

- Contrato DOM-004: PASS, 0 errores.
- Suite específica: 33/33 PASS.
- Arquitectura ejecutable: PASS después de incorporar ownership.
- Solo se utilizaron contratos y fixtures sintéticos existentes; no hubo red ni IA.

## Decisiones preservadas

- Un hash exacto prueba igualdad de bytes, no igualdad económica.
- Un provider event ID identifica una entrega dentro de connection, no un movimiento.
- Un provider record ID es candidato hasta verificar formalmente su contrato.
- Fecha + monto + dirección + referencia nunca es UNIQUE.
- Un fingerprint sirve para blocking/ranking, no para identidad.
- Un expediente dedupe puede ser único por par ordenado sin afirmar same-event.
- Misma clave con payload distinto es conflicto, no replay exitoso.
- Al menos una vez en transporte no implica efectos duplicados.
- `confirmed_same_event` no produce merge/supersession en E0.

## Revisiones requeridas

- **Accounting:** significado de same-event, reversión y futura supersession contable.
- **Architecture/Database:** índices/constraints, transacciones, pair partial unique y fencing.
- **Security:** firma previa a claim, HMAC/rotación, replay, logs y señales de conflicto.
- **Integrations:** contrato nominal por proveedor y pruebas de ID reuse/semantic drift.
- **Data Engineering:** solapamientos, locators y reglas por template/source.

## Pendientes

- Las reglas son contrato, no migraciones o handlers productivos.
- DOM-005 debe completar linaje por campo y versionado de engine/overlays.
- ARC-004 materializará eventos, outbox, retries y DLQ.
- PLT-005 probará constraints y concurrencia sobre PostgreSQL real con datos sintéticos.

## Rollback

Retirar documento/modelo/tooling/pasos CI, quitar las dos entidades de ownership y
restaurar el estado central anterior. No existen datos, migraciones ni efectos externos.

Esta entrega no supera S1-READY, DRG-00 ni habilita datos reales o auto-dedupe.

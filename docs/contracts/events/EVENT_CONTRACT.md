# Contrato de eventos v0

CloudEvents 1.0 JSON con extensiones de Fincilia.

## Semántica

- Outbox y cambio de dominio se confirman en una transacción.
- Entrega al menos una vez.
- Consumidor usa inbox único por event id.
- Orden solo por agregado, nunca global.
- Consumidores toleran duplicación y reordenamiento declarado.
- El payload lleva IDs, hashes y referencias inmutables.
- Datos sensibles completos y binarios quedan fuera del evento.

## Catálogo inicial

~~~text
fincilia.engagement.activated.v1
fincilia.engagement.suspended.v1
fincilia.engagement.revoked.v1
fincilia.authorization.changed.v1
fincilia.source.registered.v1
fincilia.artifact.received.v1
fincilia.artifact.quarantined.v1
fincilia.artifact.accepted.v1
fincilia.artifact.rejected.v1
fincilia.artifact.purged.v1
fincilia.processing_run.requested.v1
fincilia.processing_run.completed.v1
fincilia.processing_run.failed.v1
fincilia.dataset.validated.v1
fincilia.dataset.published_complete.v1
fincilia.dataset.published_partial.v1
fincilia.dataset.superseded.v1
fincilia.completeness.evaluated.v1
fincilia.account_balance.recorded.v1
fincilia.match_run.requested.v1
fincilia.match_run.completed.v1
fincilia.match.proposed.v1
fincilia.match.confirmed.v1
fincilia.match.rejected.v1
fincilia.match.reversed.v1
fincilia.exception.opened.v1
fincilia.exception.resolved.v1
fincilia.reconciliation_statement.calculated.v1
fincilia.close.closed.v1
fincilia.close.reopened.v1
fincilia.report_snapshot.created.v1
fincilia.usage.recorded.v1
fincilia.usage.credited.v1
~~~

Cada tipo requiere un schema de data antes de implementación.


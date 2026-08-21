# Máquinas de estado v0

~~~text
Artifact:
received → quarantined → accepted | rejected | purged

ImportJob:
queued → running → waiting_for_mapping | failed | cancelled | completed

Dataset:
draft → validated → partial_unverified | published_complete → superseded

MatchRun:
queued → running → review_required → completed | failed | cancelled

Period:
planned → collecting → reconciling → review → ready_to_close → closed → reopened
~~~

## Reglas

- Transiciones se ejecutan por comandos autorizados, no por updates arbitrarios.
- Cada transición registra actor, versión, razón y audit event.
- Partial/unverified sirve para investigar, no para certificar.
- Reabrir crea nueva revisión; no reescribe el snapshot cerrado.
- Cancelación no equivale a rollback de efectos ya publicados.


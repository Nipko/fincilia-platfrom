# Contrato de jobs v0

## Fuentes de verdad

- PostgreSQL conserva autorización, definición y estado de dominio visible.
- Temporal conserva historial durable de workflow.
- Valkey conserva porcentaje/heartbeat efímero.

## Invariantes

- El adaptador no reintenta.
- La cola reintenta trabajo stateless.
- Temporal posee timers, compensaciones y espera humana.
- Worker recibe capacidad corta para empresa, job y objetos exactos.
- Worker no publica directamente estado financiero.
- Monolito valida manifiesto y revalida autorización antes de publicar.
- Output incompleto nunca aparece como completed.
- Agotar presupuesto produce DLQ/estado visible/responsable.


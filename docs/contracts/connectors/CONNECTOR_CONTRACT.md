# Contrato de conectores v0

Todo conector declara:

1. País, institución, fuente y tipos de cuenta.
2. Autorización, scopes, revocación y secret references.
3. Backfill, incremental, cursor y ventana histórica.
4. IDs estables, pending/posted y correcciones.
5. Paginación, rate limits y frescura.
6. Webhook, firma, timestamp, nonce y replay.
7. Totales y completitud por periodo.
8. Taxonomía de errores; sin retries internos.
9. SLA, status y modo degradado.
10. Región, subencargados, DPA y retención.
11. Unidad de costo, moneda y mínimos.
12. Fallback por archivo.
13. Sandbox, fixtures sintéticos y golden tests.
14. Owner, versión y política de retiro.

## Gate de certificación

- Contract tests.
- Replay/duplicados.
- Cursor y paginación.
- Pending→posted/correcciones.
- Rate limit y expiración.
- Completitud/control totals.
- Revocación/borrado.
- Aislamiento cross-company.
- Fallback y modo degradado.
- Legal, SLA y costo aprobados.

Archivos permanecen fallback contractual aunque exista API.


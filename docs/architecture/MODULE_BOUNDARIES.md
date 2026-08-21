# Límites de módulos

- Estado: Draftable
- Gate: S1-READY

| Módulo | Escribe | Expone | Prohibido |
|---|---|---|---|
| IAM/Access | subjects, identities, memberships, grants | authorize/revoke | Leer payload financiero |
| Tenancy | organization, company, engagement | activar/suspender/transferir | Mover histórico |
| Sources | fuentes, conexiones, expectativas | registrar/sync request | Secretos en DB |
| Ingestion | artefactos, cuarentena, runs | aceptar/rechazar/procesar | Publicar movimiento |
| Clean | datasets, source records, recetas, overlays, linaje | validar/publicar | Modificar raw |
| Finance | cuentas, saldos, obligaciones, movimientos | comandos canónicos | Leer tablas de ingesta |
| Reconciliation | completitud, candidates, decisions, statements | proponer/confirmar/revertir | Confirmar por LLM |
| Close | ciclos, aprobaciones, snapshots | cerrar/reabrir | Cerrar sin gates |
| Reporting | definiciones, snapshots, schedules | generar/exportar | Autorizar desde warehouse |
| Risk | señales e investigaciones | abrir/resolver | Declarar fraude |
| Usage/Billing | entitlements y usage ledger | registrar uso/crédito | Bloquear lectura/exportación |
| Platform | outbox, inbox, jobs, releases | dispatch/reconcile | Ser verdad financiera |
| Audit | índice append-only | registrar evidencia | Actualizar/borrar eventos |

## Reglas

- Un módulo no escribe tablas de otro.
- Invariantes inmediatas usan comandos síncronos dentro del monolito.
- Eventos sirven para efectos posteriores y proyecciones.
- Workers devuelven manifiestos; el monolito valida y publica.
- Reporting, Risk y Analytics no autorizan acciones financieras.
- AI Gateway no posee tablas financieras ni endpoints de mutación.


---
task_id: FNC-CLS-002
status: REVIEW_PENDING
base_sha: 042a91c
reservation_sha: df8bda7
backend_sha: 7330580
web_sha: 692a04a
journey_sha: 96f5edf
tested_head_sha: 96f5edf
integration_sha: pending
data_ceiling: synthetic_only
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Accounting, Security, Backend/Architecture, Product, Accessibility/QA]
---

# Handoff FNC-CLS-002 — observaciones canonicas de saldo por cuenta

## Resultado entregado

La plataforma puede registrar y consultar observaciones inmutables de saldo por
cuenta a partir de una celda visible de un dataset publicado. La empresa, cuenta,
moneda, zona horaria, release del motor y version del esquema se resuelven en el
servidor; el cliente solo selecciona la fila, las columnas de importe y fecha y
el tipo de saldo.

La observacion no se presenta como conciliacion ni como prueba de cierre. Hasta
materializar el camino completo de linaje, cada nueva fila queda en
`required_pending`, se muestra como pendiente y bloquea la preparacion de cierre.

## Persistencia y reglas financieras

- `V0026__canonical_account_balance.sql` crea `account_balance` company-scoped,
  con RLS forzada, dinero `numeric(38,12)`, moneda explicita, instante UTC,
  coordenadas y huellas de los campos fuente, release y esquema no nulos.
- La clave compuesta obliga a que cuenta, moneda y empresa pertenezcan al mismo
  contexto. Solo una relacion fuente-cuenta activa puede aportar el saldo.
- Solo se acepta un dataset publicado, completo, verificado y con linaje
  completo. La coordenada debe existir en la evidencia persistida.
- La escritura es append-only para la aplicacion: `SELECT` e `INSERT`, sin
  `UPDATE` ni `DELETE`; el worker no tiene privilegios sobre la tabla.
- La repeticion exacta es idempotente. Una observacion distinta para la misma
  evidencia, cuenta, tipo y fecha se rechaza con conflicto.
- La fecha local de la fuente se convierte al final del dia en su zona horaria y
  luego a UTC. El importe usa el convenio decimal versionado del mapeo y
  aritmetica `Decimal`; no hay conversion mediante `float`.

`V0027__balance_evidence_link_is_current_authority.sql` es la correccion
forward-only de un hallazgo de ejecucion: una relacion administrativa creada
despues de la fecha economica puede ser la autoridad vigente. La validacion exige
estado activo y ausencia de `valid_to`, sin comparar `valid_from` con la fecha
del extracto. `V0026` no se reescribio tras aplicarse localmente.

## API, autorizacion y auditoria

- `GET /companies/{company_id}/balances` requiere `movement.read` y devuelve el
  historico autorizado por RLS.
- `GET /companies/{company_id}/balances/evidence` y
  `POST /companies/{company_id}/balances` requieren `close.prepare`.
- La vista de evidencia esta acotada a 50 filas. Valores crudos solo aparecen en
  el flujo sintetico explicito; el modo de datos reales permanece bloqueado.
- Empresa, cuenta y moneda enviados por el cliente no se aceptan como autoridad.
- La auditoria registra identificadores, indices, tipo, moneda y estado de linaje,
  pero no el importe ni el contenido de las celdas.
- Fuera de contexto, sin permiso, con mezcla entre empresas, formato ambiguo,
  celda vacia o indice fuera de rango, el flujo falla cerrado.

## Experiencia web y diagnostico de cierre

La ruta `/empresas/{companyId}/saldos` ofrece una estacion visual para escoger
la fila de evidencia, tipo de saldo, columna de importe y columna de fecha. La
cuenta, fuente y moneda derivadas son visibles antes de registrar. El historico
muestra importe exacto, coordenadas y estado de linaje sin convertir el dinero a
numero JavaScript.

El lector puede consultar el historico; solo quien tenga `close.prepare` ve y
ejecuta la preparacion. El centro de cierre ahora distingue saldos ausentes de
saldos observados pero inelegibles. Sigue manteniendo `close_ready: false` y
`can_execute_close: false`: `reconciliation_statement` y el cierre productivo
continuan deliberadamente no disponibles.

La inspeccion en navegador integrado comprobo la jerarquia visual, seleccion de
evidencia, advertencia de no cierre, historico, coordenadas y etiqueta
`Pendiente`, sin desbordes ni ambiguedad de accion.

## Evidencia ejecutada

| Verificacion | Resultado |
|---|---|
| API unitaria completa | 129 pruebas, OK |
| Dominio focal de saldos y close-readiness | 12 pruebas, OK |
| PostgreSQL/RLS focal de saldos | 2 pruebas, OK |
| PostgreSQL de cierre + saldos | 4 pruebas, OK |
| Web unitaria completa | 188 pruebas en 30 ficheros, OK |
| TypeScript, ESLint y build Next productivo | OK; ruta `/saldos` incluida |
| E2E focal de saldos | 1 prueba, OK |
| E2E focal de close-readiness | 1 prueba, OK |
| Accesibilidad focal Axe | 0 violaciones, OK |
| Accesibilidad web completa | 14 pruebas, OK |
| Regresion Chromium completa | 24 de 25; unica falla conocida de fixture persistente REC-002 |
| Migraciones locales | V0026 y V0027 aplicadas; migraciones anteriores sin cambio de checksum |
| Quality gate y contratos estructurales | OK |
| S1-READY | evaluacion valida; 39/40, unicamente revision humana independiente |
| Stack local | API, web, worker, PostgreSQL, Valkey y MinIO saludables |

La unica falla del recorrido Chromium completo es preexistente: REC-002 busca un
expediente abierto, pero el unico fixture de la base persistente ya esta en
estado terminal por una corrida anterior. No se borro ni reabrio el ledger
append-only para forzar verde. Los recorridos focales nuevos pasan y CI crea un
entorno fresco.

## Hallazgos y limites abiertos

1. El primer trigger comparaba `valid_from` de la relacion fuente-cuenta con la
   fecha economica. PostgreSQL real demostro que esa fecha administrativa puede
   ser posterior; V0027 separa correctamente ambos conceptos.
2. `account_balance` ya era entidad del contrato canonico, pero la implementacion
   fisica completa del linaje por campo aun no existe. Marcar la observacion como
   `complete` habria creado evidencia falsa; por eso queda `required_pending`.
3. `reconciliation_statement`, partidas conciliatorias y evaluaciones de
   completitud aun no son entidades canonicas productivas. Deben entrar primero
   por contrato/ADR y despues por esquema, productor, consumidor y E2E.
4. No se implementan excepciones contables, snapshot, cierre, reapertura, firma,
   reporte certificado, IA, movil ni datos reales.

## Revision humana requerida

- Accounting: tipos de saldo, instante economico, signo, moneda y evidencia
  minima que volvera elegible una observacion.
- Security + Backend/Architecture: RLS, grants, trigger, idempotencia, auditoria y
  el criterio de autoridad vigente de V0027.
- Product + Accessibility/QA: seleccion de celdas, lenguaje fail-closed,
  historial, estados y recorrido accesible.

`FOUNDER-01`, el implementador y los usuarios sinteticos no cuentan como
revisores independientes.

## Rollback

La API y la ruta web pueden retirarse sin tocar evidencia. No se ejecuta down
migration sobre una tabla financiera. Si el contrato cambia, se agrega una
migracion forward-only; las observaciones sinteticas ya creadas permanecen
inmutables y auditables. V0027 puede corregirse solo con otra migracion hacia
adelante.

## Rutas liberadas

V0026/V0027 y pruebas PostgreSQL, modulo y rutas API de saldos,
`close_readiness.py`, cliente/accion/ruta/estilos/pruebas web, ficha, handoff y
registros centrales de FNC-CLS-002.

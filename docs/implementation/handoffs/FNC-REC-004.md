---
task_id: FNC-REC-004
status: REVIEW_PENDING
base_sha: 94142c2
reservation_sha: cca3ff3
implementation_sha: cefd9a0
web_sha: 9b6547c
tested_head_sha: 9b6547c
integration_sha: 792198b
data_ceiling: synthetic_only
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Accounting, Security, Database, Backend/Architecture, Accessibility/QA]
---

# Handoff FNC-REC-004 — exclusividad uno-a-uno de confirmaciones

## Resultado entregado

Una confirmacion humana reserva exactamente los dos movimientos del candidato.
La clave primaria `(company_id, movement_id)` impide que cualquiera de ellos
quede confirmado con otra contraparte, incluso si dos decisiones llegan en
paralelo. Propuestas superpuestas y rechazos siguen permitidos.

La confirmacion conserva `financial_effect: none` y
`proves_balance_reconciliation: false`: no cambia movimientos, no suma importes,
no crea grupos, no resuelve completitud y no habilita cierres.

## Implementacion

- V0025 agrega `match_confirmation_member`, RLS forzada, FKs company-scoped,
  privilegios minimos y append-only. El runtime solo puede leer la proyeccion.
- `reserve_confirmed_match_members` se ejecuta desde el trigger de una decision
  `confirmed` y materializa ambos lados en una sentencia. Su owner controlado es
  `fincilia_dispatch`, no se concede `EXECUTE` directo y DB-G03 sigue pendiente.
- La API hace una comprobacion explicativa, pero la autoridad final es la PK. La
  mutacion vive en un savepoint: perder la carrera revierte decision, auditoria
  allowed y recibo, y deja confirmar la auditoria denied en la transaccion padre.
- Los listados exponen `confirmation_conflict`; la web retira solo el boton de
  confirmar, explica la causa y conserva el rechazo explicito.
- El cliente web conserva el codigo RFC 7807 de la API separado del detalle, de
  modo que presenta un mensaje acotado sin depender de texto interno.

## Evidencia ejecutada

| Verificacion | Resultado |
|---|---|
| Migracion principal V0001→V0025 | V0025 aplicada; checksum `04e6e5c…` |
| Replay de migraciones | `head: V0025`, `applied: []`, `mutated: false` |
| PostgreSQL/API/MinIO focal | 2 pruebas, OK; carrera real `200/409` |
| API completa en imagen | 117 pruebas, OK |
| Migration readiness | 64 pruebas y validador, OK |
| Web unitarias | 176 en 28 ficheros, OK |
| Web lint, TypeScript y build | OK; imagen de produccion reconstruida |
| Navegador integrado | confirmado + rechazado + abierto conflictivo visibles; solo rechazo disponible en el conflicto |
| Stack local | API, web, worker, PostgreSQL, Valkey y MinIO saludables |

La prueba focal demuestra un solo ganador concurrente, dos miembros exactos,
insercion directa bloqueada por la misma PK, ausencia de decision/recibo/auditoria
allowed del perdedor, auditoria denied durable, RLS y ledger no borrable por el
runtime. El expediente perdedor puede rechazarse despues del conflicto.

## Hallazgos de ejecucion

1. El primer intento de V0025 fallo atomicamente al transferir la funcion porque
   el owner controlado no tenia `CREATE` sobre el esquema. La migracion final
   concede ese privilegio solo dentro de la transaccion y lo revoca de inmediato.
2. El segundo intento fallo atomicamente porque el trigger se creaba despues de
   revocar `EXECUTE` al migrador. La version finalmente aplicada crea el trigger
   mientras el migrador aun es dueño y sella la funcion despues.
3. Auditar `allowed` antes de una restriccion concurrente sin savepoint deja la
   sesion abortada y hace imposible registrar la denegacion. El savepoint une
   decision, reserva, recibo y auditoria permitida como un solo efecto reversible.
4. La bandeja real dejo un tercer expediente abierto que comparte el movimiento
   confirmado. Fue evidencia visual util: muestra el conflicto sin ocultar el
   expediente ni ofrecer una segunda confirmacion.

## Revision humana y limites

- Accounting debe aceptar la exclusividad uno-a-uno como semantica provisional;
  grupos N:M, asignaciones parciales y reversals siguen fuera de alcance.
- Security/Database deben revisar el definer, RLS, privilegios, trigger y PK.
- Backend/Architecture debe revisar el savepoint y el codigo de conflicto.
- Product/Accessibility/QA debe revisar el lenguaje y que rechazo permanezca
  disponible sin presentar el estado como conciliacion de saldos.

ADR-027 permanece `Proposed`; DB-G03 y S1-READY no cambian. `FOUNDER-01`, el
implementador y los usuarios sinteticos no cuentan como revisores independientes.

## Rollback

La aplicacion puede retirar el indicador y volver a una respuesta generica sin
tocar datos. V0025 es forward-only: no se elimina la tabla ni sus reservas. Un
forward fix compatible seria obligatorio. Revertir el trigger en aplicacion
antes de otro esquema seria inseguro porque permitiria dobles confirmaciones.

## Rutas liberadas

V0025, prueba PostgreSQL, reconciliacion API/web, prueba adjudicada de migration
readiness, ADR-027, ficha, handoff y registros centrales de FNC-REC-004.

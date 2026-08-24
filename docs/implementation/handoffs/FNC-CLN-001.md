---
task_id: FNC-CLN-001
status: REVIEW_PENDING
base_sha: 595fcad
reservation_sha: 2a0bcf7
head_sha: 7f05ce9
data_ceiling: synthetic_only
gate_effect: none
reviewers_pending: [Accounting, Security, Database, Product, QA]
---

# Handoff FNC-CLN-001 — propuestas tipadas de corrección

## Resultado

La plataforma permite proponer una corrección tipada sobre una fila de un
dataset validado, compararla con el valor vigente y someterla a revisión de una
persona distinta. Aprobar no actualiza el movimiento: deja la propuesta como
`approved` y bloquea publicar el dataset base hasta que FNC-CLN-002 la aplique
en una versión nueva.

El flujo conserva raw, source record y movimiento; no habilita auto-match,
cierre, datos reales, IA ni móvil. ADR-026 sigue `Proposed`.

## Implementación

- V0016 crea `field_overlay` y `field_overlay_review` append-only, con valores
  tipados acotados, RLS forzada, claves compuestas company/dataset/movement,
  SoD en trigger y cero UPDATE/DELETE para `fincilia_app`.
- La API resuelve target y source record server-side, normaliza decimal exacto,
  fechas ISO, moneda y dirección, usa digest base para concurrencia optimista y
  serializa propuestas/revisiones con advisory locks transaccionales.
- Pendiente y aprobada-no-aplicada son blockers distintos de publicación. Una
  propuesta rechazada no muta ni bloquea el dataset.
- El audit log recibe IDs, campo, razón y desenlace; nunca copia el nuevo valor.
  Las denegaciones se registran sin lanzar dentro de la transacción que las
  conserva.
- La web ofrece propuesta desde el detalle del movimiento y revisión desde el
  puesto del dataset. Siempre distingue `aprobada` de `aplicada`.

## Evidencia ejecutada

| Verificación | Resultado |
|---|---|
| Migración sobre PostgreSQL 17 real | V0016 aplicada; segunda pasada `mutated: false`, head V0016 |
| `db.tests.test_field_overlays` | 6 pruebas, OK, PostgreSQL + MinIO reales |
| API completa | 70 pruebas, OK |
| Web lint + TypeScript | OK |
| Web unitarias | 79 pruebas, 14 ficheros, OK |
| Web build Next production | OK, 11 rutas |
| `tools.work_graph.validate` | OK, una reserva activa |
| `tools.test_catalog.cli validate` | `model_valid: true`, cero blockers |
| `tools.migration_readiness.validate` | OK, V0001..V0016 descubiertas |
| `git diff --check` | OK; solo avisos CRLF→LF existentes |

La prueba real cubre: caso feliz, propuesta concurrente con un solo ganador,
stale/no-op, tipo inválido, target/cross-company neutro, autor que intenta
autorrevisar, revisión única, rechazo que desbloquea, aprobación que bloquea el
dataset base, movimiento inmutable y denegación de UPDATE/DELETE al runtime.

## Defectos encontrados al ejecutar

1. `SELECT ... FOR UPDATE` exigía UPDATE sobre la tabla append-only. Se cambió
   por advisory lock por overlay sin ampliar privilegios.
2. La primera limpieza de integración no fijaba contexto RLS y no veía sus
   overlays. La suite ahora fija empresa antes de retirar cada fixture.
3. Dos propuestas simultáneas podían haber calculado la misma secuencia. El
   advisory lock por company/dataset/movement/field deja un ganador y el otro
   recibe 409 estable.
4. Una denegación lanzada dentro del bloque transaccional habría perdido su
   audit. La ruta conserva primero el evento y levanta el RFC 7807 después.

## Pendientes y decisiones humanas

- El usuario autorizó explícitamente integrar V0016 como migración protegida.
  Quedó en `b23c29a`; la web quedó en `7f05ce9` y ambos quality gates pasaron
  sobre su índice exacto.
- Accounting/Security/Database deben revisar ADR-026 y V0016. Ninguna aprobación
  se infiere de las pruebas.
- `quality_gate.cli` debe volver a ejecutarse con las rutas indexadas; su corrida
  actual fue verde sobre el índice anterior y no se presenta como cobertura del
  diff no indexado.
- FNC-CLN-002 debe aplicar solamente overlays `approved`: crear processing run y
  dataset nuevos, recalcular digest/manifest, escribir `lineage_row_override`,
  conservar la versión base y resolver el blocker sin UPDATE destructivo.

## Rollback

Antes de cualquier dato permitido —hoy solo hay fixtures sintéticos— el rollback
de esquema es: retirar router/consumidores; eliminar trigger y función; eliminar
reviews y overlays sintéticos; retirar las dos tablas y las dos unicidades
compuestas añadidas. Después de existir evidencia, no se borran propuestas: se
desactiva la escritura y se conserva lectura/auditoría hasta una migración de
retirada revisada.

## Orden de integración propuesto

1. `b23c29a`: backend/esquema/pruebas — V0016, API y 70+6 pruebas.
2. `7f05ce9`: web — cliente BFF, acciones, formularios, cola y 79 pruebas/build.
3. Este cierre libera la reserva y deja revisión independiente pendiente sin
   modificar S1-READY.

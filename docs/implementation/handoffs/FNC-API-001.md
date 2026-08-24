# Handoff — FNC-API-001: Creacion atomica y segura de mapeos

| Campo | Valor |
|---|---|
| Tarea | `FNC-API-001` |
| Alias | `FNC-P4.1` |
| Estado | **`REVIEW_PENDING`** |
| Base | `0d9f022` |
| `tested_head_sha` | `0726a11` |
| Rama | `claude/principal-dev` |
| Implementacion | Codex principal dev + Integration Steward |
| Revisores pendientes | Backend, Security, Database, QA |
| Datos | Completamente sinteticos |
| Gate | `S1-READY` sigue `not_met`; esta tarea no lo mueve |
| Migraciones | Ninguna modificada; V0001–V0015 verificadas sin mutacion |

## Resultado

La creacion de un mapeo tiene ahora una frontera transaccional propia alrededor
de la plantilla y su primera version. Dentro de la sesion HTTP esa frontera es
un savepoint: si falla la segunda insercion, la primera se revierte incluso si
un consumidor futuro decide capturar la excepcion y continuar la transaccion.

La ruta resuelve artefacto y fuente bajo el contexto RLS fijado por el servidor.
Una referencia malformada, inexistente o ajena produce el mismo 403; un nombre
duplicado dentro de la empresa produce `mapping-name-conflict` con 409; cualquier
otro error sigue emergiendo como error servidor y ya no se disfraza de acceso
denegado.

## Cambios

- `apps/api/src/fincilia_api/datasets.py`
  - savepoint atomico para las dos inserciones;
  - traduccion cerrada por nombre de constraint para `uq_mapping_name`,
    `fk_mapping_source` y `fk_mapping_version_artifact`;
  - los demas errores de integridad no se silencian.
- `apps/api/src/fincilia_api/routes.py`
  - fuente y artefacto se resuelven bajo RLS antes de escribir;
  - UUID malformado conserva la respuesta neutral;
  - 409 estable para nombre duplicado y eliminacion del `except Exception`.
- `db/tests/test_p3_vertical.py`
  - fuente cross-company y malformada: 403 y cero filas;
  - duplicado secuencial: una plantilla, una version y una auditoria;
  - carrera de dos solicitudes: un 201, un 409 y ningun huerfano;
  - fallo real de FK en la segunda insercion: conteo posterior `(0, 0)`;
  - `RuntimeError` sintetico: se propaga y no se convierte en 403.

No se tocaron migraciones, seeds, permisos, RLS, contratos financieros, web,
mobile, worker, CI ni infraestructura.

## Matriz de aceptacion

| Criterio | Evidencia |
|---|---|
| AC-01/02 | Prueba cross-company/malformada y pre-resolucion RLS de ambas referencias |
| AC-03 | Prueba de FK en segunda insercion y carrera concurrente; conteos directos en PostgreSQL |
| AC-04 | Dos POST con mismo nombre: 201/409, una plantilla y una version |
| AC-05 | Traduccion por constraints permitidos y prueba de error inesperado |
| AC-06 | Duplicado y carrera conservan exactamente un evento `dataset.map` permitido |
| AC-07 | 5 pruebas adversariales, vertical de 38 y suite API de 65 en verde |
| AC-08 | Plan V0001–V0015: `mutated: false`; diff sin migraciones |

## Verificacion reproducida

1. Imagen local `migrate` reconstruida desde el worktree.
2. Aplicador de migraciones: `head: V0015`, `applied: []`, `mutated: false`, exit 0.
3. Cinco pruebas adversariales dirigidas: **5 OK** en 7.192 s.
4. `python -m unittest db.tests.test_p3_vertical -v`: **38 OK** en 33.231 s.
5. `python -m unittest discover -s /app/tests -t /app/tests -v`: **65 OK**.
6. `python -B -m tools.work_graph.validate`: `ok: true`, 2 reservas antes
   de liberar esta tarea.
7. `python -B -m tools.test_catalog.cli validate`: `ok: true`, sin hallazgos
   bloqueantes; 13 planeados y 41 contractuales aun no implementados, preexistentes.
8. `python -B -m tools.quality_gate.cli`: `ok: true`, cero hallazgos sobre el indice.

El primer intento dirigido no ejecuto pruebas: Docker habia reiniciado MinIO y
Valkey durante la reconstruccion y el contenedor no pudo resolver `objectstore`.
Se reanudaron ambos servicios, quedaron sanos y la repeticion completa paso. No
se rebajo ninguna comprobacion para resolverlo.

## Decisiones y limites preservados

- La unicidad sigue siendo la definida por `uq_mapping_name`; no se cambio a una
  comparacion aproximada ni se creo unicidad con datos financieros.
- La respuesta 409 corrige una clasificacion previa incorrecta; no amplia datos
  expuestos ni cambia el cuerpo de exito.
- No se agrego idempotency key. Repetir el mismo nombre es un conflicto visible,
  no una reutilizacion silenciosa.
- No se permitieron datos reales, IA, conectores ni aplicacion movil.
- Ningun owner humano, ADR o gate fue aceptado.

## Revision y riesgos pendientes

- Backend debe revisar que las dos excepciones de dominio son la frontera
  adecuada para consumidores futuros.
- Security debe confirmar la equivalencia de 403 para referencias no visibles.
- Database debe revisar el savepoint y la lista exacta de constraints traducidos.
- QA debe repetir la carrera en CI sobre el commit integrado.
- `display_name` conserva la sensibilidad a mayusculas definida hoy por V0008;
  cambiarla requeriria una decision y migracion separadas.
- CI remoto no se ejecuto en este tramo local.

## Commits y rollback

- `01c9e74` — reserva y ficha de la tarea.
- `6808e54` — implementacion atomica y errores estables.
- `0726a11` — pruebas adversariales PostgreSQL.

El rollback funcional consiste en revertir `0726a11` y `6808e54`. No hay
migracion ni transformacion de datos que deshacer. La reserva/documentacion se
libera por separado al integrar este handoff.

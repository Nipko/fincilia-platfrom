# Handoff — FNC-WEB-002: Puesto web de revision y excepciones

| Campo | Valor |
|---|---|
| Tarea | `FNC-WEB-002` (`FNC-P4.2`) |
| Estado | **`REVIEW_PENDING`** |
| Base | `bf0c023` |
| `tested_head_sha` | `c627789` |
| Rama | `claude/principal-dev` |
| Implementacion | Codex principal dev + Integration Steward |
| Revisores pendientes | Product/Accounting, Security, Accessibility/QA |
| Datos | Completamente sinteticos |
| Gate | `S1-READY` sigue `not_met`; la tarea no lo mueve |
| Migraciones y permisos | Ninguno modificado |

## Resultado

El puesto de mapeo permite revisar la version mas reciente del dataset antes de
publicarla. La API devuelve los impedimentos de publicacion calculados por la
misma funcion de dominio que usa el POST de publicacion; la web ya no reconstruye
estado, aprobacion de release, segregacion de funciones ni vigencia de overrides.

La persona con `dataset.publish` ve los overrides vigentes, puede aprobar una
excepcion critica creada por otra persona o rechazar el dataset con un motivo.
Los formularios solo transportan identificadores y el motivo: no incluyen
valores financieros ni digests. Cada accion vuelve a ligar los identificadores
ocultos al dataset y al documento que la persona esta viendo.

## Cambios funcionales

- `apps/api/src/fincilia_api/datasets.py`
  - el listado expone `needs_approval` y `approved` desde el contrato de dominio;
  - la web no mantiene una segunda lista de campos criticos.
- `apps/api/src/fincilia_api/routes.py` y commit previo de esta tarea
  - `GET dataset` entrega `publish_blockers` y `can_publish` coherentes;
  - lectura y publicacion comparten el evaluador de estado, SoD, release y overrides.
- `apps/web/src/lib/api.ts`
  - cliente server-only para listar/aprobar overrides y rechazar datasets;
  - el tipo renderizado omite deliberadamente los digests devueltos por la API.
- `apps/web/src/app/actions.ts`
  - aprobacion y rechazo revalidan company/dataset/artifact antes de mutar;
  - 401, 403, 409 y 422 no se convierten en exito ni en listas vacias.
- puesto de mapeo
  - muestra blockers autoritativos y metadatos de excepciones;
  - ofrece aprobacion independiente, rechazo motivado y feedback accesible;
  - no muestra una accion que el rol no posee.
- pruebas
  - identificador de override ajeno y dataset de otro documento son rechazados;
  - motivo vacio o mayor a 200 caracteres no llega a la API;
  - SoD, estado invalido y permiso insuficiente conservan mensajes distintos;
  - PostgreSQL demuestra el cambio de readiness tras aprobacion independiente.

No se tocaron migraciones, RLS, permisos, seeds, workers, CI, contratos, ADR,
gates, conectores, IA ni aplicacion movil.

## Matriz de aceptacion

| Criterio | Evidencia |
|---|---|
| AC-01/02 | `publication_blockers` compartido por lectura y publicacion; pruebas PostgreSQL de pendiente/aprobada |
| AC-03 | tabla web con campo, tipo, motivo, autor y estado; sin valor financiero |
| AC-04/05 | accion vuelve a listar por dataset, backend conserva SoD y la ruta se revalida al aprobar |
| AC-06 | rechazo exige motivo y vuelve a comprobar el artefacto visible |
| AC-07 | pruebas unitarias diferenciadas para 403, 409 y 422; 401 conserva redireccion comun |
| AC-08 | etiquetas, `required`, `maxLength`, estados pending y feedback `alert/status`; solo IDs ocultos |
| AC-09 | 15 integraciones y 62 unitarias; lint, tipos y build en verde |
| AC-10 | diff y quality gate confirman ausencia de migraciones, permisos, gates y mobile |

## Verificacion reproducida

1. `node node_modules/eslint/bin/eslint.js .`: exit 0.
2. `node node_modules/typescript/bin/tsc --noEmit`: exit 0.
3. `node node_modules/vitest/vitest.mjs run`: **62 pruebas, 11 archivos, OK**.
4. `node node_modules/next/dist/bin/next build`: exit 0; todas las rutas compiladas.
5. Imagen `migrate` reconstruida desde `c627789` y dependencias locales sanas.
6. `python -m unittest db.tests.test_row_overrides`: **15 pruebas, OK** en 18.288 s contra PostgreSQL y MinIO reales.
7. `python -B -m tools.work_graph.validate`: `ok: true` antes de liberar la reserva.
8. `python -B -m tools.test_catalog.cli validate`: `ok: true`, cero hallazgos bloqueantes; 13 planeados y 41 contractuales no implementados, preexistentes.
9. `python -B -m tools.quality_gate.cli`: `ok: true`, cero hallazgos sobre el indice exacto de `c627789`.

El `npm` global de Windows apunta a un `npm-cli.js` inexistente. No se modifico
el equipo ni el lockfile: se ejecutaron directamente los binarios locales que
corresponden a las versiones fijadas en `package-lock.json`.

## Limites y revision pendiente

- Product/Accounting debe validar lenguaje y suficiencia del puesto para el
  proceso de revision de un contador.
- Security debe revisar la religadura de IDs, la exposicion acotada de autor y
  que el listado API conserve los digests solo en servidor.
- Accessibility/QA debe repetir el recorrido autenticado y accesibilidad en CI.
- El autor se presenta como ocho caracteres del subject UUID; no se invento un
  directorio de nombres. Una mejora necesita un contrato de identidad separado.
- La pantalla revisa la version mas reciente del documento, igual que el flujo
  P3 actual. Comparar versiones historicas queda fuera de esta rebanada.
- CI remoto no fue observado en este tramo local. Ningun revisor, ADR o gate fue
  aceptado por el implementador.

## Commits y rollback

- `20cc5ef` — reserva, ficha y registro de la tarea.
- `15e7aa9` — readiness autoritativo en la API.
- `c627789` — puesto web, acciones y pruebas adversariales.

Revertir `c627789` y `15e7aa9` restaura el flujo anterior. No hay migracion,
transformacion de datos ni permiso que deshacer. La documentacion y liberacion
de rutas se revierten por separado si la revision rechaza la rebanada.

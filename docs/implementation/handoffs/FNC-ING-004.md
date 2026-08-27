---
task_id: FNC-ING-004
status: REVIEW_PENDING
base_sha: 8aaaca645ee0b33884a202971a5c09a2d7dbbdbe
reservation_sha: 216a0c7ea02677563ead4bbe366ef7cc4cf50fe6
implementation_shas: [adb0f94, dd28b26, 9c1b7aa]
tested_head_sha: 9c1b7aa3e4aae53911d491b1534c0296fe5cc296
ci_run: https://github.com/Nipko/fincilia-platfrom/actions/runs/33038864190
ci_status: success
data_ceiling: synthetic_only
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Product, Accessibility/QA, Security, Backend/Architecture]
---

# Handoff FNC-ING-004 — bandeja web de carga multiple

## Resultado

El centro documental permite seleccionar entre uno y diez archivos para una
misma fuente y presenta validacion, progreso y resultado por documento. Cada
recepcion sigue utilizando el BFF y el endpoint individual ya autorizados por el
servidor; el navegador no introduce una autoridad ni un contrato batch nuevos.

Una carga individual conserva el recorrido anterior hacia su expediente. Un
lote permanece en el centro documental, actualiza el historico una sola vez y
ofrece un enlace estable para cada documento confirmado o ya recibido.

## Implementacion y controles

- Se validan antes de la red el nombre, el contenido, el maximo de 25 MiB por
  archivo, diez archivos y 100 MiB por seleccion. Los invalidos permanecen
  visibles y no impiden enviar los validos.
- La cola mantiene como maximo dos solicitudes en vuelo. Los fallos parciales no
  deshacen exitos y el reintento se limita a archivos fallidos o cancelados.
- Cancelar aborta solicitudes activas y evita iniciar pendientes. Un `401`
  cancela el resto del lote y dirige al ingreso sin reflejar cuerpos upstream.
- La bandeja distingue listo, subiendo, completado, ya recibido, fallido, no
  valido y cancelado. El resumen y el progreso se anuncian a tecnologias de
  asistencia.
- Sin hidratacion el formulario permanece inerte. El boton deshabilitado tiene
  un estado visual explicito y la navegacion superior conserva separacion y
  operacion por teclado.
- El filtro del historico se llama `Filtrar por fuente`, sin colisionar con el
  selector `Fuente del documento` de la bandeja.
- No se anadio migracion, dependencia, endpoint batch, inferencia de fuente,
  ZIP, reanudacion por bytes, OCR, PDF avanzado, IA, auto-mapeo, auto-match ni
  efecto financiero.

## Evidencia reproducible

| Verificacion | Resultado |
|---|---|
| Unitarias web completas | 35 archivos / 227 pruebas, OK |
| Unitarias focales de bandeja y centro | 2 archivos / 13 pruebas, OK |
| TypeScript y ESLint | OK |
| Build Next de produccion | OK, construido dentro de las imagenes locales |
| Chromium focal | limite 25 MiB + 1 byte, historico y lote de tres: 3/3, OK |
| Axe focal | bandeja antes y despues de cargar: 1/1, OK |
| Regresion Chromium aislada | 33/33, OK |
| Regresion Axe aislada | 21/21, OK |
| Limpieza del entorno E2E | Verificada; contenedores, redes y volumenes `fincilia-e2e` eliminados |
| Navegador local real | Centro, etiquetas, estados deshabilitados y jerarquia visual correctos |
| Quality gate sobre indice Git | OK |
| CI integral sobre `9c1b7aa` | Todos los jobs aplicables OK; performance omitida por contrato |

Comandos principales:

```text
npm --prefix apps/web run test:unit
npm --prefix apps/web run typecheck
npm --prefix apps/web run lint
infra/local/fincilia-local.ps1 up
npm --prefix apps/web run test:e2e -- tests/e2e/synthetic-upload.spec.ts
npm --prefix apps/web run test:e2e -- tests/e2e/document-history.spec.ts
npm --prefix apps/web run test:a11y -- tests/e2e/spreadsheet-upload.a11y.spec.ts
infra/local/test-web-isolated.ps1
python -m tools.work_graph.validate
python -m tools.quality_gate.cli
```

La primera repeticion focal recibio `Servicio no disponible` porque el stack
persistente estaba detenido, no por una denegacion funcional. Se levanto con el
wrapper documentado y la misma prueba paso. La regresion completa se ejecuto
despues en un proyecto desechable con base y object storage sinteticos propios.

## Revision, limites y despliegue

Product debe revisar la carga cognitiva, estados y recuperacion de fallos;
Accessibility/QA, teclado, anuncios y combinaciones de estado; Security y
Backend/Architecture, cancelacion, expiracion de sesion, concurrencia acotada y
reutilizacion del BFF individual. El implementador y `FOUNDER-01` no cuentan
como revisores independientes.

El rollout es exclusivamente web y expand-only. El rollback restaura el
selector unitario sin eliminar ni modificar recepciones ya confirmadas. La
funcionalidad no cambia S1-READY y continua limitada a datos sinteticos. Con
este handoff quedan liberadas todas las rutas reservadas por FNC-ING-004.

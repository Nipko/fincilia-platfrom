---
task_id: FNC-CLN-004
status: REVIEW_PENDING
base_sha: faf93927c61fd50ff23a7f5b62f581e491a51fde
reservation_sha: 61ee36abd8cc2994d7671bb8b9efcf0acec05f83
implementation_shas: [840a4bd, 978aab0, 74b9391]
tested_head_sha: 74b9391d34f3fc7afb44e40b1adea62cfef2c6ca
ci_run: https://github.com/Nipko/fincilia-platfrom/actions/runs/33035252492
ci_status: success
data_ceiling: synthetic_only
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Accounting, Data, Security, Database, Backend/Architecture, Product, Accessibility/QA]
---

# Handoff FNC-CLN-004 — preview y plantillas de limpieza

## Resultado

El estudio de mapeo ya funciona como limpiador visual antes de guardar. El
operador puede declarar una ultima fila inclusiva, excluir columnas auxiliares y
observar una muestra canonica producida por el mismo dominio determinista que
prepara el dataset. La muestra distingue movimientos, rechazos y blockers, y no
crea versiones ni movimientos.

Las configuraciones guardadas se muestran como plantillas de su misma empresa y
fuente. Una plantilla compatible se aplica a otro artefacto creando una version
inmutable bajo la misma identidad estable. La version anterior nunca se
reescribe; replay exacto y solicitudes concurrentes no duplican versiones, y el
drift de esquema falla cerrado.

## Implementacion y controles

- `last_data_row` es opcional e inclusivo. Dominio, conteos de preparacion,
  lotes y manifest usan el mismo rango y rechazan un final anterior al inicio.
- `mapping-preview` exige `dataset.map`, reutiliza los parsers de fecha, decimal
  y direccion, y solo audita conteos y codigos acotados. No persiste dataset,
  movimiento, descripcion, referencia, importe ni celda.
- Columnas asignadas e ignoradas a la vez producen un blocker explicito. El
  cliente y el servidor limitan la cantidad de indices ignorados.
- La compatibilidad de plantilla se deriva de la huella de esquema del
  artefacto destino. Empresa, fuente y artefacto se resuelven bajo RLS; las
  negativas cross-company son neutrales y no escriben.
- La web conserva el borrador al solicitar preview, presenta el rango y la
  truncacion, y marca plantillas compatibles e incompatibles antes de aplicar.
- La tabla horizontal del preview recibe foco y nombre accesible para que su
  desplazamiento sea operable con teclado, incluido Safari.
- La carga BFF no cancela lectores todavia bloqueados ni aborta un destino que
  ya respondio correctamente. El submit permanece deshabilitado en el HTML
  inicial hasta que React pueda interceptarlo, evitando una navegacion GET.
- No hubo migracion, dependencia, IA, dato real, auto-mapeo, auto-match,
  publicacion automatica ni cambio de gate.

## Evidencia reproducible

| Verificacion | Resultado |
|---|---|
| Dominio de mapeo | 52 pruebas, OK |
| PostgreSQL + API + MinIO P3 | 45 pruebas, OK; incluye 7 escenarios nuevos de rango, preview, RLS, replay, concurrencia y drift |
| Web unitaria | 34 archivos / 216 pruebas, OK |
| TypeScript y ESLint | OK |
| Build Next de produccion | OK antes del ajuste semantico `tabIndex`; TypeScript y Axe cubren el ajuste final |
| Chromium focal | rango multihoja y plantilla exacta versionada, 2/2 OK |
| WCAG automatizado focal | perfil y preview de mapeo, 1/1 Axe OK sobre el codigo fuente final |
| CI integral sobre `74b9391` | todos los jobs aplicables, Chromium y Axe, OK; performance omitida por contrato |
| Quality gate por incremento | OK |

Comandos principales:

```text
$env:PYTHONPATH='packages/contracts/python'; python -m unittest packages/contracts/python/tests/test_mapping.py
docker compose -p fincilia-local -f infra/local/compose.yaml run --rm migrate python -m unittest db.tests.test_p3_vertical
npm --prefix apps/web run test:unit
npm --prefix apps/web run typecheck
npm --prefix apps/web run lint
npm --prefix apps/web run test:e2e -- tests/e2e/synthetic-upload.spec.ts --grep "multihoja|una plantilla compatible"
npm --prefix apps/web run test:a11y -- tests/e2e/spreadsheet-upload.a11y.spec.ts --grep "ficha perfilada"
python -m tools.work_graph.validate
python -m tools.quality_gate.cli
```

La regresion aislada local completa no se repitio al final porque el disco C:
quedo por debajo de 500 MiB y una corrida anterior termino por `ENOSPC` despues
de 27 recorridos verdes. Los dos flujos nuevos y Axe se repitieron sobre la pila
persistente con bytes sinteticos unicos. La CI enlazada reproduce la pila limpia
y queda como evidencia autoritativa del conjunto completo.

## Defectos encontrados por ejecucion

1. Una accion React reseteaba controles no controlados despues del preview. El
   borrador y una revision de formulario conservan exactamente la configuracion.
2. Cancelar un `ReadableStream` bloqueado producia una promesa rechazada; abortar
   tras una respuesta upstream exitosa cerraba prematuramente el destino. Ambos
   caminos se separaron y tienen prueba.
3. Un submit antes de hidratacion ejecutaba el fallback GET nativo. El boton se
   habilita solo cuando existe manejador cliente.
4. La demo persistente exponia colisiones de nombres y documentos identicos en
   E2E. Los casos ahora usan bytes y nombres unicos y seleccionan la plantilla
   recien creada por su nombre exacto.
5. Axe detecto que el contenedor desplazable de la muestra no era enfocable.
   Ahora es una region de teclado nombrada y Axe pasa.

## Revision, limites y rollback

Accounting y Data deben revisar la semantica del rango y de los rechazos;
Security y Database, RLS, auditoria y concurrencia; Backend/Architecture, la
idempotencia; Product y Accessibility/QA, el lenguaje y la operacion con
teclado. El implementador y `FOUNDER-01` no cuentan como revisores
independientes. S1-READY no cambia.

El rollback funcional oculta preview y reutilizacion, y vuelve a omitir el final
de rango. No se borra evidencia ni se reescriben versiones existentes; no hay
migracion que revertir. Con este handoff quedan liberadas todas las rutas
reservadas por FNC-CLN-004.

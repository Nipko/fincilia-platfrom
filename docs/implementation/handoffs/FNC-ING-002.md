---
task_id: FNC-ING-002
status: REVIEW_PENDING
base_sha: 7b1f1259f3bdc9846a6f44c6eb4b03a31836d93b
reservation_sha: 47b28835f9078eef88370cd24240b74202a39c45
implementation_shas: [3d293d2, 4d2c755, 9155fb7]
ci_hardening_sha: 92fcca9aa08d583113a68e46e3614063271fdbed
tested_head_sha: 92fcca9aa08d583113a68e46e3614063271fdbed
ci_run: https://github.com/Nipko/fincilia-platfrom/actions/runs/33030858209
data_ceiling: synthetic_only
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Security, Data, Database, Backend/Architecture, Product, Accessibility/QA]
---

# Handoff FNC-ING-002 — seleccion multihoja y limpieza visual

## Resultado

La plataforma puede recibir un XLSX sintetico seguro con varias hojas visibles
sin elegir una por accidente. Tras escanear el libro completo, la web presenta
un inventario sin valores de celda, exige que el operador elija una hoja y solo
entonces encola perfil y extraccion. La hoja seleccionada llega al estudio de
mapeo, donde se pueden declarar la fila de cabecera, la primera fila de datos y
las columnas que deben ignorarse sin borrar ni reescribir la evidencia original.

El flujo XLSX seguro de una sola hoja sigue siendo automatico. Formulas, macros,
enlaces externos, partes activas y paquetes inseguros siguen fallando cerrado y
nunca se ejecutan. La release del scanner sube de `scan-2` a `scan-3` para que la
nueva politica pueda reevaluar artefactos anteriores sin mutar decisiones.

## Implementacion, seguridad y linaje

- V0037 agrega `spreadsheet_selection`, inmutable, company-scoped y protegida
  con RLS. `UPDATE` y `DELETE` permanecen denegados.
- El endpoint de seleccion resuelve empresa y permisos en el servidor. El
  cliente solo aporta la identidad opaca de hoja; nombre, ordinal y visibilidad
  se validan contra el manifiesto seguro que produjo el scanner.
- Repetir la misma seleccion es idempotente; elegir otra hoja para el mismo
  artefacto devuelve conflicto y una identidad desconocida falla con 422.
- Perfil y extraccion consumen exactamente `sheet_identity` y conservan ordinal
  fisico, fila, columna y celda A1 en el localizador de origen.
- Un libro multihoja no crea `raw_record` antes de la seleccion. La web tampoco
  ofrece avanzar al mapeo mientras el estado siga pendiente.
- El manifiesto expuesto contiene identidad, nombre, ordinal y estado de hoja;
  nunca valores financieros ni transcripciones de celdas.
- No se agregaron dependencias, IA, datos reales, auto-mapeo, auto-match ni
  capacidad de cierre.

## Evidencia reproducible

| Verificacion | Resultado |
|---|---|
| Contratos Python | 351 pruebas, OK |
| PostgreSQL focal sobre V0037 | 14 escenarios, OK; seleccion, idempotencia, conflicto, RLS y privilegios |
| Web unitaria | 34 archivos / 213 pruebas, OK |
| TypeScript, ESLint y build Next | OK |
| Chromium aislado | 30/30, OK; incluye multihoja, hoja correcta y columnas ignoradas |
| WCAG automatizado | 19/19 Axe, OK; incluye selector multihoja |
| Migracion limpia | V0001..V0037, OK |
| Limpieza del laboratorio | contenedores, redes y volumenes desechables retirados, OK |
| CI sobre `92fcca9` | 5 jobs obligatorios, success; performance omitida por diseño |
| Work graph y quality gate por incremento | OK |

Comandos principales:

```text
python -m unittest discover -s packages/contracts/python/tests -v
python -m unittest db.tests.test_quarantine_before_raw -v
npm --prefix apps/web run test:unit -- --reporter=dot
npm --prefix apps/web run typecheck
npm --prefix apps/web run lint
npm --prefix apps/web run build
.\infra\local\test-web-isolated.ps1
python -m tools.work_graph.validate
python -m tools.quality_gate.cli
```

La ejecucion aislada termino en 160,3 segundos sobre PostgreSQL limpio, con los
30 recorridos funcionales y las 19 comprobaciones Axe verdes. La corrida CI de
GitHub sobre `92fcca9` termino verde y reprodujo contratos, migraciones, RLS,
API, worker, ciclo local, Chromium y Axe; el carril de rendimiento fue omitido
por diseño porque solo se ejecuta bajo demanda.

## Limites, revision y rollback

Esta rebanada permite una seleccion inmutable por artefacto. Procesar otra hoja
del mismo libro requiere cargarla como evidencia independiente; fusion de hojas
y datasets derivados multihoja necesitan un contrato posterior. No hay XLS
binario, ODS, PDF/OCR, ejecucion de formulas ni borrado fisico de evidencia.

Security y Data deben revisar el manifiesto y el parser cerrado; Database, RLS,
privilegios y V0037; Backend/Architecture, idempotencia y despacho; Product y
Accessibility/QA, la seleccion y limpieza visual. El implementador y
`FOUNDER-01` no cuentan como revisores independientes. S1-READY no cambia.

El rollback funcional retira el selector y el despacho multihoja, conservando
selecciones y evidencia inmutables. V0037 solo se corrige hacia delante; nunca
se edita una migracion aplicada. Quedan liberadas todas las rutas reservadas.

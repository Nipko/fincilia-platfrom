---
task_id: FNC-ING-001
status: REVIEW_PENDING
base_sha: e3b37b40d482b92e415691623c31718ccd445e6c
reservation_sha: 3ca4157
implementation_sha: 4a2e75f
test_hardening_sha: 52fabc6a6f87ed019cf9c075f913409899f45fd5
tested_head_sha: 52fabc6a6f87ed019cf9c075f913409899f45fd5
data_ceiling: synthetic_only
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Security, Data, Database, Backend/Architecture, Product, Accessibility/QA]
---

# Handoff FNC-ING-001 — ingesta segura de XLSX

## Resultado

La plataforma acepta ahora un XLSX completamente sintetico de una sola hoja y
lo lleva por el recorrido existente de carga, escaneo, perfilado, extraccion,
preview y mapeo. El tipo se decide inspeccionando el paquete OPC y no por la
extension. La extraccion conserva coordenadas 1-based de libro, hoja, fila,
columna y celda A1, y nunca usa `float` para representar dinero.

El alcance permanece cerrado: formulas, macros, contenido embebido, conexiones
externas, XML con DTD/entidades, ZIP inseguro, mas de una hoja visible o limites
excedidos terminan en cuarentena con una causa estable y sin `raw_record`.

## Implementacion y seguridad

- `spreadsheet.py` procesa ZIP/XML con biblioteca estandar y limites de entradas,
  expansion, filas, columnas, longitud de celda y tiempo.
- El scanner `scan-2` recorre las partes relevantes antes de promover y permite
  reevaluar decisiones anteriores sin reescribirlas.
- Perfil y resumen publican estructura, tipos y conteos, pero no transcriben
  valores del documento.
- V0036 amplia `origin_locator` solo con la variante `spreadsheet` validada; no
  relaja RLS, privilegios ni la inmutabilidad de evidencia.
- Web distingue XLSX, muestra la hoja y conserva el flujo humano de mapeo y
  publicacion ya existente.
- No se agregaron dependencias, IA, datos reales, auto-mapeo, auto-match ni
  capacidad de cierre.

## Evidencia reproducible

| Verificacion | Resultado |
|---|---|
| Contratos de ingesta/linaje | 347 pruebas, OK |
| Worker documental | 19 pruebas, OK |
| PostgreSQL focal XLSX | 2 escenarios, OK |
| Migracion limpia | V0001..V0036, OK |
| Web unitaria | 213 pruebas, OK |
| TypeScript, ESLint y build Next | OK |
| Chromium focal | 4/4, OK; carga XLSX, preview y continuidad al mapeo |
| Axe focal XLSX | 1/1, OK |
| Runtime local persistente | API `ready`, esquema V0036, web 200; seis servicios sanos |
| Work graph y quality gate por incremento | OK |

Comandos principales:

```text
python -m unittest discover -s packages/contracts/python/tests -v
python -m unittest discover -s workers/document/tests -v
npm --prefix apps/web run test:unit -- --reporter=dot
npm --prefix apps/web run typecheck
npm --prefix apps/web run lint
.\infra\local\test-web-isolated.ps1
python -m tools.work_graph.validate
python -m tools.quality_gate.cli
```

La regresion PostgreSQL de 362 casos se ejecuto tambien sobre la demo persistente.
El flujo XLSX y 360 casos pasaron; dos fallos finales dependieron de residuos de
corridas previas (limpieza de `processing_run` y una cola no vacia). Se corrigio
y comprobo por separado una limpieza anterior que bloqueaba por referencias de
overlays. La autoridad de regresion integral es la CI sobre PostgreSQL nuevo,
pendiente al momento de redactar este handoff.

## Limites, revision y rollback

Permanecen fuera XLS binario, ODS, PDF/OCR y libros multihoja o activos. Security
y Data deben revisar el parser cerrado y los limites; Database, V0036;
Backend/Architecture, el despacho; Product y Accessibility/QA, el recorrido.
`FOUNDER-01` y el implementador no cuentan como revisores independientes.

S1-READY no se promueve. El rollback funcional retira el despacho XLSX y deja la
evidencia ya escrita inmutable. V0036 solo se corrige hacia delante; nunca se
edita una migracion aplicada. Quedan liberadas todas las rutas de FNC-ING-001.

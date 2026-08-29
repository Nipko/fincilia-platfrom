---
task_id: FNC-ING-005
status: REVIEW_PENDING
base_sha: cd911de
implementation_shas: [7cf4909, 3cbd3a8]
tested_head_sha: 4ba6d08
data_ceiling: synthetic_only
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Security, Data, Backend/Architecture, Product, Accessibility/QA]
---

# Handoff FNC-ING-005 — ODS seguro y formatos honestos

## Resultado integrado

Un ODS tabular completamente sintetico ya recorre la misma tuberia segura de un
XLSX: firma interna, inspeccion de paquete/XML, escaneo minimizado de PAN y
secretos, promocion, seleccion de hoja, perfil sin valores, extraccion por
tandas y localizador `spreadsheet` con digest, hoja, ordinal y fila.

El scanner subio a `scan-4`, por lo que un ODS previamente conservado por falta
de analizador se puede reevaluar sin reescribir la decision anterior. CSV y XLSX
mantienen su comportamiento. La interfaz dice explicitamente que CSV/XLSX/ODS
seguros se procesan y que PDF/ZIP generico solo se conservan en cuarentena.

## Controles implementados

- El tipo ODS se decide por el `mimetype` interno, nunca por `.ods`.
- El paquete rechaza rutas ambiguas, duplicados case-insensitive, symlinks,
  cifrado, entradas/expansion excesivas, DTD, entidades y XML mal formado.
- Scripts, macros, formulas, enlaces, objetos, partes binarias, celdas fusionadas
  y contenido activo nunca se ejecutan ni se promueven.
- Repeticiones ODS se expanden solo dentro de limites de filas, columnas y texto;
  padding vacio no fabrica columnas publicadas.
- Numeros se leen con `Decimal` y se serializan en punto fijo, nunca con `float`.
- Una hoja visible se procesa automaticamente. Varias hojas producen solo un
  manifiesto sin valores y exigen la seleccion company-scoped ya existente.
- Perfil y resumen solo describen forma; los valores viven exclusivamente en
  `raw_record` bajo el mismo control RLS y de arriendo del worker.
- El recorrido E2E uso un ODS construido deterministicamente en memoria y datos
  exclusivamente sinteticos; no se incorporo ningun documento externo.

## Evidencia reproducible

| Verificacion | Resultado |
| --- | --- |
| Contratos Python completos | 365 pruebas, OK |
| Worker aislado en Compose | 20 pruebas, OK |
| Web focal de carga | 7 pruebas, OK |
| TypeScript | OK |
| Build Next en imagen local | OK |
| Migraciones existentes | V0001–V0042, `mutated: false` |
| Stack local | PostgreSQL, Valkey, MinIO, API, worker y web sanos |
| Chromium ODS end-to-end | 1/1, carga→perfil→extraccion→mapeo, OK |
| Quality gate del primer incremento | 0 hallazgos |

Comandos principales:

```text
python -m unittest discover -s packages/contracts/python/tests -t packages/contracts/python/tests
docker compose -f infra/local/compose.yaml -p fincilia-local run --rm --no-deps worker python -m unittest discover -s /app/tests -t /app/tests
sh infra/local/up.sh
npm --prefix apps/web run typecheck
npm --prefix apps/web run test:e2e -- tests/e2e/synthetic-upload.spec.ts --grep "ODS seguro"
python -m tools.quality_gate.cli
```

## Limites deliberados

Esto no es un parser universal ni antivirus. El subconjunto ODS es tabular y
pasivo; un documento ordinario con thumbnail, imagen, objeto, firma, macro,
formula, enlace o parte no explicada queda bloqueado en vez de interpretarse a
medias. PDF, imagen, XLS binario y ZIP generico continúan sin promocion. OCR y
antimalware requieren una tarea separada con aislamiento, limites de CPU/memoria,
motor fijado, corpus hostil y politica de falsos positivos.

No se movio S1-READY, DRG-00 ni DRG-01. Security debe revisar superficies XML y
ZIP; Data, exactitud y coordenadas; Backend/Architecture, consumo y reintento;
Product/Accessibility/QA, estados y lenguaje. El implementador y `FOUNDER-01`
no cuentan como revisores independientes.

## Rollback

Volver a `SCANNER_RELEASE=scan-3` y retirar el despacho `ods`. Las decisiones,
objetos y registros existentes permanecen inmutables; no hay migracion que
revertir. Con este handoff quedan liberadas las rutas de FNC-ING-005.

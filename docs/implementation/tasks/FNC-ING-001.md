---
id: FNC-ING-001
title: Ingesta segura de XLSX sintetico de una sola hoja
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: e3b37b40d482b92e415691623c31718ccd445e6c
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Security, Data, Database, Backend/Architecture, Product, Accessibility/QA]
---

# Resultado esperado

Permitir que un libro XLSX completamente sintetico, sin macros, formulas,
contenido activo ni enlaces externos y con una sola hoja de calculo sea
inspeccionado de principio a fin, promovido, perfilado, extraido y recorrido en
el estudio de importacion con localizadores exactos de hoja, fila y celda.

# Autoridad

- ADR-001 aisla parsing en el worker y prohibe que publique estado financiero.
- ADR-005 exige localizador por hoja, fila, columna y celda.
- ADR-024 conserva la coordenada variable en `raw_record.origin_locator` y la
  combina con la columna del plan versionado.
- El modelo de linaje ya declara `spreadsheet`/`xlsx`, base ordinal uno y macro
  execution `forbidden`; esta tarea materializa ese contrato sin ampliarlo.
- Plan unificado secciones 7.4 y 8 prioriza XLS/XLSX, extraccion fiel, formulas
  no ejecutadas y seleccion explicita de estructura. Esta rebanada solo cubre
  XLSX de una hoja; XLS binario y seleccion multihoja permanecen fuera.

# Rutas reservadas

- `packages/contracts/python/fincilia_contracts/ingestion.py`, `profiling.py`,
  `extraction.py`, `lineage.py`, `spreadsheet.py` y pruebas focales.
- `workers/document/src/fincilia_worker/jobs.py`, `main.py` y pruebas focales.
- `db/migrations/V0036__spreadsheet_origin_locator.sql` y pruebas de migracion.
- API/web de empresa, documento, preview, mapeo y pruebas focales cuando sea
  necesario para presentar el formato sin alterar el flujo CSV.
- fixtures XLSX exclusivamente sinteticos y generador determinista de la tarea.
- documentacion local, esta ficha, handoff y registros centrales por el
  Integration Steward.

# Fuera de alcance

- XLS binario, ODS, PDF, imagen, OCR, XML, OFX o conectores externos.
- Libros con macros, formulas, enlaces externos, objetos embebidos, consultas o
  mas de una hoja; se conservan en cuarentena con motivo estable.
- Elegir hojas, rangos o tablas desde la web; fusionar hojas; ejecutar formulas.
- Auto-mapeo financiero, auto-match, cierre, datos reales, IA o movil.
- Promover gates, aceptar ADR o sustituir revisiones humanas independientes.

# Criterios de aceptacion

- **AC-01.** El tipo se decide por la estructura interna OPC, nunca por la
  extension. ZIP renombrado, macro, XML con DTD/entidades y contenido activo no
  se promueven.
- **AC-02.** El escaneo recorre todas las partes relevantes del libro bajo
  limites de entradas, expansion y tamano, detecta secretos sin copiarlos y solo
  promueve un XLSX de una hoja sin formulas ni conexiones externas.
- **AC-03.** Perfil y resumen no transcriben valores; declaran hoja, conteos,
  columnas, tipos, celdas con formula y cualquier truncamiento.
- **AC-04.** La extraccion conserva valores mostrados deterministas, nunca
  ejecuta formula y asigna a cada fila un localizador `spreadsheet` 1-based con
  workbook, hoja, fila y cardinalidad. La celda reconstruida coincide con A1.
- **AC-05.** La base admite solo localizadores delimitados o spreadsheet con
  forma y rangos validos; cualquier JSON incompleto, tipo desconocido o celda
  incoherente falla cerrado. RLS y privilegios existentes no se relajan.
- **AC-06.** El mismo libro produce el mismo perfil, registros, digests y
  localizadores. Fechas seriales reconocidas se muestran como ISO y el valor
  almacenado queda ligado por digest, sin `float` financiero.
- **AC-07.** Un XLSX sintetico completa carga, preview, mapeo y publicacion bajo
  las mismas reglas humanas y de completitud del CSV; un libro no soportado
  muestra una causa estable y no crea `raw_record`.
- **AC-08.** Unitarias, golden, PostgreSQL real, worker, API/web, E2E, Axe,
  lint, tipos, build, quality gate y CI pasan; S1-READY sigue sin promover.

# Rollout y rollback

Rollout local y sintetico. `SCANNER_RELEASE` cambia para que una decision previa
de cuarentena pueda reevaluarse sin reescribirla. El rollback retira el despacho
XLSX y deja sus decisiones y `raw_record` inmutables; V0036 se revierte solo por
forward-fix, nunca editando migraciones aplicadas.

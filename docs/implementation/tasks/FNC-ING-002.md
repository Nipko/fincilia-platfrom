---
id: FNC-ING-002
title: Seleccion explicita de hoja XLSX y limpieza visual web
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 7b1f1259f3bdc9846a6f44c6eb4b03a31836d93b
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Security, Data, Database, Backend/Architecture, Product, Accessibility/QA]
---

# Resultado esperado

Permitir que un libro XLSX sintetico con varias hojas seguras sea promovido sin
interpretar una hoja por accidente. La web presenta el inventario sin valores,
el operador elige explicitamente una hoja visible y solo entonces se encolan el
perfil y la extraccion. El estudio de mapeo conserva la limpieza visual por fila
de cabecera, primera fila de datos y columnas ignoradas.

# Autoridad y limites

- ADR-001 mantiene el parsing en el worker.
- ADR-005 y ADR-024 exigen coordenadas fisicas reproducibles.
- FNC-ING-001 aporta el lector OPC seguro, la cuarentena de contenido activo y
  el flujo XLSX de una hoja que debe permanecer compatible.
- `source_artifact` es evidencia inmutable. La seleccion no modifica el libro.
- Esta primera version permite una seleccion inmutable por artefacto. Procesar
  otra hoja requiere un artefacto independiente; el soporte multi-seleccion se
  decidira en una tarea posterior con identidad propia de dataset.

# Rutas reservadas

- `packages/contracts/python/fincilia_contracts/spreadsheet.py`, `ingestion.py`,
  `profiling.py` y pruebas focales.
- `workers/document/src/fincilia_worker/jobs.py`, `main.py` y pruebas focales.
- `db/migrations/V0037__spreadsheet_selection.sql` y pruebas PostgreSQL.
- API/web de documentos, seleccion de hoja, preview y mapeo, con sus pruebas.
- esta ficha, handoff y registros centrales integrados por el Integration Steward.

# Fuera de alcance

- XLS binario, ODS, PDF/OCR, macros, formulas, conexiones o contenido activo.
- Fusionar hojas, seleccionar varias hojas del mismo artefacto o ejecutar formulas.
- Borrar o reescribir extracciones, datos reales, IA, auto-match, cierre o movil.
- Promover gates, aceptar ADR o sustituir revision humana independiente.

# Criterios de aceptacion

- **AC-01.** El escaner inspecciona todas las partes y textos antes de promover;
  un libro seguro multihoja queda pendiente de seleccion, no en cuarentena.
- **AC-02.** El inventario expone solo identidad, nombre, ordinal y visibilidad;
  nunca valores de celda. Hoja oculta o identidad ajena falla cerrado.
- **AC-03.** La seleccion es company-scoped, RLS, idempotente por contenido e
  inmutable; una seleccion divergente devuelve conflicto estable.
- **AC-04.** Perfil y extraccion usan exactamente la identidad seleccionada y
  conservan hoja/fila/celda fisica en el linaje.
- **AC-05.** XLSX seguro de una sola hoja sigue procesandose automaticamente.
- **AC-06.** La web permite elegir hoja y explica la limpieza visual posterior:
  cabecera, inicio de datos y columnas descartadas, sin afirmar que borra evidencia.
- **AC-07.** Pruebas unitarias, PostgreSQL, worker, API, web, E2E/Axe y quality
  gate aplicables pasan; CI queda verde y S1-READY no cambia.

# Rollout y rollback

Rollout local y exclusivamente sintetico. El scanner sube de release para poder
reevaluar libros antes puestos en cuarentena sin reescribir decisiones. El
rollback deja de ofrecer seleccion y conserva decisiones, seleccion y evidencia;
el esquema se corrige hacia delante y las migraciones aplicadas no se editan.

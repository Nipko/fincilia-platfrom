---
id: FNC-ING-005
title: Ingesta segura de ODS y contrato honesto de formatos
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: cd911de
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Security, Data, Backend/Architecture, Product, Accessibility/QA]
---

# Resultado esperado

Permitir que una hoja ODS completamente sintetica, sin formulas, scripts,
objetos, enlaces ni contenido embebido, recorra escaneo, seleccion explicita,
perfil, extraccion y linaje con las mismas garantias del flujo XLSX. La web
distingue los formatos procesables de los que solo puede conservar en
cuarentena, sin prometer PDF/OCR o ZIP generico antes de contar con un analizador
aislado y antimalware real.

# Autoridad y dependencias

- ADR-001 mantiene todo parsing de documentos en el worker.
- ADR-004 exige cuarentena antes de promocion y evidencia inmutable por zona.
- ADR-005 y ADR-024 exigen coordenadas fisicas reproducibles.
- FNC-ING-001/002 aportan el contrato seguro de hoja, seleccion y linaje.
- El techo vigente es exclusivamente sintetico; esta tarea no mueve DRG-00/01.

# Rutas reservadas

- `packages/contracts/python/fincilia_contracts/open_document.py`,
  `ingestion.py`, `profiling.py` y pruebas focales.
- `workers/document/src/fincilia_worker/jobs.py`, `main.py`, README y pruebas.
- Web de carga/documentos y pruebas focales para presentar capacidades reales.
- Documentacion de plataforma, esta ficha, handoff y registros centrales por el
  Integration Steward.

# Fuera de alcance

- PDF/OCR, imagen, XLS binario, OFX, XML libre, archivos ODS cifrados o firmados.
- ZIP como lote, macros, formulas, scripts, objetos, enlaces o contenido activo.
- Antivirus simulado, IA, datos reales, auto-mapeo, auto-match, cierre o movil.
- Promover gates, aceptar ADR o sustituir revision humana independiente.

# Criterios de aceptacion

- **AC-01.** ODS se identifica por `mimetype` interno, no por extension, y solo
  se promueve tras inspeccionar el paquete y todos sus XML permitidos.
- **AC-02.** Rutas ambiguas, cifrado, DTD/entidades, formulas, scripts, enlaces,
  objetos, contenido binario, repeticion expansiva y bombas quedan bloqueados.
- **AC-03.** El inventario multihoja no transcribe valores; una hoja visible se
  procesa automaticamente y varias exigen seleccion explicita e inmutable.
- **AC-04.** Perfil y extraccion son deterministas, usan decimal/texto exacto y
  conservan hoja, ordinal, fila y digest bajo `locator_kind=spreadsheet`.
- **AC-05.** El escaneo de PAN/secretos ve el texto logico completo, pero sus
  hallazgos nunca copian el valor encontrado.
- **AC-06.** CSV/XLSX/ODS se presentan como procesables. PDF y ZIP generico se
  presentan como conservados en cuarentena, no como analizados ni compatibles.
- **AC-07.** Pruebas de contratos, worker, web y quality gate aplicables pasan;
  S1-READY y los gates de datos reales conservan su estado.

# Rollout y rollback

Rollout sintetico y expand-only. `SCANNER_RELEASE` cambia para reevaluar ODS
previamente puesto en cuarentena sin reescribir decisiones. El rollback retira
el despacho ODS y conserva evidencia, decisiones y registros ya creados; no hay
migracion destructiva.

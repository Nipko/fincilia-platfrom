# Encargo para Claude — FNC-DOM-005

Copia desde la siguiente sección hasta “FIN DEL ENCARGO”.

---

Trabajas en el repositorio compartido de Fincilia. Ejecuta exclusivamente la tarea
`FNC-DOM-005` sobre la base declarada `a43bc1c`. Otro agente puede trabajar al mismo
tiempo en arquitectura/CI; no debes tocar rutas compartidas o ampliar el alcance.

## Lectura obligatoria antes de editar

Lee completos, en este orden:

1. `AGENTS.md`
2. `CURRENT_PHASE.md`
3. `docs/implementation/OWNERSHIP.md`
4. `docs/implementation/tasks/FNC-DOM-005.md`
5. `docs/implementation/DEFINITION_OF_READY.md`
6. `docs/implementation/DEFINITION_OF_DONE.md`
7. `docs/domain/LINEAGE_SPEC.md`
8. `docs/domain/CANONICAL_MODEL.md`
9. `docs/domain/canonical-model.json`
10. `docs/domain/EVIDENCE_DEDUPE_IDEMPOTENCY.md`
11. `docs/domain/idempotency-dedupe.json`
12. `docs/domain/COMPLETENESS_BALANCES.md`
13. `docs/architecture/MODULE_BOUNDARIES.md`
14. `docs/architecture/module-boundaries.json`
15. `docs/architecture/DFD.md`
16. `docs/architecture/dfd-flows.json`
17. `docs/security/THREAT_MODEL.md`
18. `docs/security/threat-model.json`
19. `docs/privacy/PRIVACY_MAP.md`
20. `docs/privacy/privacy-map.json`
21. `docs/testing/SYNTHETIC_DATA_POLICY.md`
22. `docs/testing/TEST_CATALOG.md`
23. `docs/implementation/decision_requests/FNC-PRV-001-FINDINGS.md`
24. `docs/adr/ADR-004-object-storage-evidence-zones.md`
25. `docs/adr/ADR-005-field-lineage.md`
26. `docs/adr/ADR-006-recipes-overlays.md`
27. `docs/adr/ADR-023-engine-release.md`
28. `docs/implementation/templates/HANDOFF.md`

Antes de editar confirma en el handoff: base declarada, rutas, dependencias, datos
autorizados y comandos. Si no puedes verificar Git porque está prohibido, declara la
limitación; no la suplas inventando un SHA.

## Objetivo

Convertir el seed `LINEAGE_SPEC.md` en un contrato completo y ejecutable para:

1. localizadores de origen por formato;
2. linaje por campo y por decisión de extremo a extremo;
3. overlays manuales no destructivos, reversibles y concurrentemente seguros;
4. `engine_release` inmutable y reproducible;
5. reprocesamiento que crea versiones y diffs sin reescribir históricos.

Este bloque sigue siendo contrato de Fase 0. No implementes almacenamiento productivo,
migraciones, parsers, OCR real, conectores, UI ni IA externa.

## Rutas que puedes modificar

- `docs/domain/LINEAGE_SPEC.md` — ampliar el seed existente; no crear un documento rival.
- `docs/domain/lineage-model.json` — nuevo modelo ejecutable autoritativo.
- `tools/lineage_model/**` — validador y pruebas solo con biblioteca estándar de Python.
- `docs/implementation/handoffs/FNC-DOM-005.md` — nuevo handoff reproducible.

No modifiques ninguna otra ruta. En particular, no toques:

- `AGENTS.md`, `CURRENT_PHASE.md`, backlog, ownership, traceability o gates;
- `docs/implementation/tasks/FNC-DOM-005.md` o cualquier otra ficha de tarea;
- CI, workflows, Compose, lockfiles o archivos raíz;
- ADR, C4, DFD, threat model o privacy map;
- `canonical-model.json`, `module-boundaries.json` o contratos DOM-002/003/004;
- apps, workers, packages, SQL, migraciones o fixtures;
- archivos de otros agentes.

No uses Git: no hagas add, commit, checkout, pull, reset, stash, rebase ni config. El
Integration Steward integrará tus rutas y actualizará CI/estado en un commit posterior.

## Decisiones que debes preservar

- Company es frontera financiera estable; todo nodo/edge financiero es company-scoped.
- Raw, artifact version, origin locator y cierres históricos son inmutables.
- Corregir crea overlay o nueva versión; nunca edita evidencia de origen.
- Todo campo publicado y toda decisión financiera tiene camino completo hasta evidencia.
- Un reprocess crea `dataset_version`; nunca reescribe registros, informes o snapshots previos.
- Engine release fija exactamente qué código/artefactos produjeron un resultado.
- Fecha/monto/referencia/fingerprint no son identidad dura.
- Un LLM no calcula dinero, confirma match, autoriza acceso ni cierra.
- IA/OCR/modelos son productores versionados de propuesta/evidencia, no autoridad.
- Datos `unknown`, lineage incompleto o release no verificable bloquean publicación/cierre.
- Valkey y analytics no son fuente de verdad.
- Solo datos inequívocamente sintéticos; cero red y cero proveedores externos.
- No aceptes decisiones Legal/Privacy abiertas. Los tags personales son un eje ortogonal
  versionado y `pending_human`, no una taxonomía legal inventada por ti.

## 1. Modelo de nodos y caminos

Define tipos de nodo distintos, como mínimo:

- `artifact_version`;
- `raw_locator`;
- `extracted_field`;
- `transformed_value`;
- `source_record_field`;
- `financial_fact_field`;
- `decision` (dedupe, match, excepción, balance, cierre);
- `report_field`;
- `close_snapshot_field`.

Cada nodo debe incluir identidad inmutable, company cuando aplique, clasificación
operativa, referencia a versión y digest del valor/payload sin colocar el valor raw en
logs. No uses un JSON libre sin schema/version/tamaño.

`lineage_edge` debe ser append-only e incluir como mínimo: company, from/to tipados,
operation, processing run, engine release, canonical schema, receta/paso, overlay si
aplica, rule/reference-data/model versions, actor/workload, timestamp y audit reference.

El grafo debe:

- ser acíclico;
- impedir edges cross-company;
- impedir targets o source versions inexistentes/superseded sin declaración;
- conservar aristas de versiones anteriores;
- permitir drill-down hasta artifact/hash + locator exacto;
- distinguir “derivado de” de “decidido usando” y “incluido en snapshot”.

Define paths mínimos obligatorios. Un campo de `source_record` requiere
artifact→locator→extracted→transformed→published. Un hecho financiero añade
source_record→financial fact. Una decisión/reporte/cierre añade sus nodos finales. La
cobertura debe ser 100%; no se permite un promedio que oculte campos sin linaje.

## 2. Origin locators tipados

No uses un locator universal opaco. Modela discriminated unions y convenciones exactas:

- CSV/TSV: artifact version, encoding/dialect version, record/field ordinal, header ref y
  byte span cuando esté disponible.
- XLSX: workbook/sheet identity, row/column 1-based, celda A1, valor mostrado y fórmula
  como metadatos/digests; nunca ejecutar macro.
- PDF/imagen: página 1-based, sistema/unidad de coordenadas, bounding box, token/region
  IDs y versión OCR; incertidumbre visible.
- XML/DIAN: namespace URI, path estructural con ordinal, atributo/texto y byte span si
  existe; no XPath ejecutable suministrado por usuario.
- OFX/MT940/API: record ordinal o stable handle, field/tag path, provider/source version y
  raw span cuando corresponda.

Todo locator referencia `artifact_version_id` y hash exacto. Define validaciones de bounds,
base ordinal, coordenadas, sheet/page y máximo de tamaño. La ambigüedad produce estado
`invalid` o `review_required`, nunca un locator fabricado.

## 3. Overlays no destructivos

`field_overlay` debe ser append-only y contener:

- company/dataset/target field y versión base;
- digest y tipo del valor esperado;
- nuevo valor tipado o acción explícita de redacción, nunca código arbitrario;
- motivo estructurado + comentario acotado;
- actor, autorización/version, instante, engine/schema/recipe versions;
- riesgo del campo, approval state, audit event y overlay que revierte/sustituye.

Requisitos:

- optimistic concurrency: overlay contra base stale genera conflicto;
- aplicación determinística por cadena/version; nada de “last write wins” por reloj;
- undo/reversal crea otro overlay;
- raw/extracted originales no cambian;
- overlays de monto, moneda, dirección, cuenta, identidad fiscal o fechas contables
  requieren revisión independiente/SoD antes de alimentar decisiones;
- overlay pendiente/rechazado no alimenta publicación, match, cierre o reporte certificado;
- schema drift invalida aplicación silenciosa y exige nueva versión/revisión;
- export/reprocess manifiesta exactamente qué overlay set se aplicó.

No definas una UI. Sí define el contrato que la UI deberá mostrar para explicar original,
valor efectivo, autor, razón, diferencia y estado.

## 4. Engine release y reproducibilidad

`engine_release` pertenece a Platform según ownership existente. Define un manifest
inmutable con al menos:

- ID y semver;
- source commit SHA verificable y estado de árbol limpio;
- SHA-256 de cada artefacto ejecutable/contenedor;
- SBOM digest y formato/version;
- dependency/lock digest y build provenance;
- canonical schema compatibility;
- parsers/OCR/models/rules incluidos y sus digests/versiones;
- clasificación `neutral` o `affects_results`;
- firma/attestation reference, builder identity y build timestamp;
- estado draft/candidate/approved/revoked con aprobación humana separada;
- evaluation report/corpus manifest cuando afecta resultados.

No conviertas “approved” en algo que un agente pueda autootorgarse. Una release revocada
no desaparece: sigue referenciable para explicar históricos, pero no produce nuevos runs.

Una release `affects_results` requiere corpus adjudicado, diff de resultados y revisión.
Una release `neutral` debe demostrar equivalencia byte-for-byte en los outputs dentro del
scope declarado; si no la demuestra, se clasifica `affects_results`.

Define `reproducibility_manifest` con input artifact/version/hash, dataset, mapping
template, recipe, overlays ordenados, reference datasets, parser/model/rules, engine
release, schema, locale, timezone, deterministic config/random seed y output digests.
Mismo manifest debe producir mismos bytes canónicos o fallar explícitamente. No prometas
reproducibilidad si un proveedor/modelo externo no ofrece versión fijable.

## 5. Reprocesamiento, diffs e históricos

- Reprocess siempre crea processing run y dataset version nuevos.
- Registra `supersedes` sin borrar la versión anterior.
- Calcula diff tipado por campo/registro/decisión y monto exacto cuando aplique.
- Propaga impact analysis a hechos, matches, statements, reports y close snapshots.
- Un snapshot cerrado permanece apuntando a su release/version set original.
- Reabrir o republicar crea revisión N+1 con razón/aprobación; no cambia N.
- Si falta binario/release/input requerido, el estado es `not_reproducible` y bloquea una
  afirmación exacta; no se sustituye silenciosamente por “latest”.
- Retención/borrado de lineage sigue L-01 y tombstones; linaje no es excusa para conservar
  payload personal eliminado. Define referencias mínimas/segregadas sin inventar plazos.

## 6. Eje de privacidad pendiente

El hallazgo DR-PRV-001 exige separar sensibilidad financiera de condición personal. En
este contrato solo define el mecanismo de propagación:

- `operational_classification` y `personal_data_tags` son campos distintos;
- tags incluyen `catalog_version` y estado `pending/approved`, sin inventar contenido legal;
- una transformación no puede bajar/eliminar tags sin regla de minimización/redacción
  versionada y evidencia;
- lineage, overlay, export, IA y borrado transportan ambos ejes;
- ausencia de decisión Privacy/Legal permanece `unknown` y bloquea egress externo cuando
  el propósito lo requiera.

No edites privacy-map ni resuelvas DR-PRV-001.

## 7. Modelo ejecutable y validador

`docs/domain/lineage-model.json` debe ser la fuente estructurada autoritativa. El validador
`tools/lineage_model/validate.py` debe cargar también, en modo read-only:

- `docs/domain/canonical-model.json`;
- `docs/architecture/module-boundaries.json`;
- `docs/domain/idempotency-dedupe.json`;
- `docs/privacy/privacy-map.json` si requiere validar referencias existentes.

Extrae dinámicamente, sin listas paralelas que den cobertura falsa, las entidades/campos
con `lineage_required` del modelo canónico y las referencias de privacidad pertinentes.
Como mínimo debe enlazar PA-03, PA-06, PA-07, PA-08, PA-09, PA-15 y PA-17, además de
L-01-DERIVED, L-01-FINANCIAL, L-01-AUDITABLE-DECISION, L-01-AUDIT,
L-01-DELETE-LEDGER y L-01-BACKUP cuando el contrato los use.

Valida referencias, ownership, sets requeridos, paths, aciclicidad conceptual, company
scope, mutabilidad, overlays, reproducibilidad, releases, privacy tags y gates. Solo
biblioteca estándar; determinista, sin red/reloj y con errores estables `{code, location,
message}`. El CLI imprime JSON y retorna código distinto de cero al fallar.

Incluye funciones puras y testeadas para validar un grafo sintético, aplicar una cadena de
overlays determinísticamente y calcular `reproduction_key` mediante JSON canónico +
SHA-256. No implementes persistencia.

## 8. Pruebas obligatorias

Incluye como mínimo estos escenarios; puedes ampliar, no degradar:

- `TST-LIN-001`: path completo para 100% de campos publicados/decisiones.
- `TST-LIN-002`: campo publicado sin edge bloqueado.
- `TST-LIN-003`: edge cross-company rechazado.
- `TST-LIN-004`: ciclo rechazado.
- `TST-LIN-005`: locator fuera de bounds/ambiguo rechazado.
- `TST-LIN-006`: formato desconocido exige review, no locator inventado.
- `TST-OVR-001`: overlay no muta raw/extraction.
- `TST-OVR-002`: base stale causa conflicto.
- `TST-OVR-003`: undo es overlay append-only.
- `TST-OVR-004`: orden efectivo determinístico.
- `TST-OVR-005`: campo financiero crítico exige SoD.
- `TST-OVR-006`: overlay pendiente no alimenta publicación/cierre.
- `TST-PAR-001`: mismo manifest produce mismo output digest.
- `TST-PAR-002`: `affects_results` sin evaluación se rechaza.
- `TST-PAR-003`: `neutral` sin equivalencia byte-for-byte se rechaza.
- `TST-PAR-004`: build dirty/hash/SBOM ausente se rechaza.
- `TST-PAR-005`: reprocess crea versión, no overwrite.
- `TST-PAR-006`: snapshot histórico conserva release/version set.
- `TST-PAR-007`: release revocada no ejecuta runs nuevos.
- `TST-PRV-001`: transformación no baja tags personales silenciosamente.

La suite debe incluir tests de mutación que demuestren que el validador “muerde”. No basta
probar JSON parseable. Incluye el caso legítimo identical de DOM-004 para asegurar que
linaje no se use como dedupe destructivo.

## Entrega y verificación

Ejecuta desde la raíz:

```powershell
python -m tools.lineage_model.validate
python -m unittest tools.lineage_model.test_validate -v
python -m unittest discover -s tools/lineage_model -p "test_*.py"
python -m tools.canonical_model.validate
python -m tools.idempotency_model.validate
```

No ejecutes ni modifiques el quality gate si tus archivos aún no están indexados: registra
`pending_integration_steward`. Sí ejecuta checks locales de JSON, Markdown, merge markers,
TODO/FIXME sin task ID, datos sensibles y scope de rutas.

## Handoff requerido

El handoff debe incluir:

- base declarada y limitación de verificación;
- rutas exactas;
- cantidades de nodos/locators/paths/reglas/tests;
- comandos y resultados exactos;
- decisiones preservadas;
- contradicciones o hallazgos fuera de scope sin editar sus rutas;
- riesgos y revisiones requeridas de Data, Accounting, Architecture, Security y Privacy;
- rollback;
- instrucciones concretas para Integration Steward: indexar, quality gate, integrar CI,
  actualizar CURRENT_PHASE/backlog/traceability y completar `integration_sha`.

Deja estado `REVIEW_PENDING` o `PARTIAL`. No declares S1-READY, DRG-00, producción lista,
cumplimiento legal, retención aceptada ni release aprobada. No uses datos reales.

Si encuentras una contradicción material, no la resuelvas fuera de alcance: documéntala
en el handoff y continúa las partes no bloqueadas. Detente solo si impide un contrato
coherente completo.

FIN DEL ENCARGO

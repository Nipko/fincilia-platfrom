# Especificación de linaje v0.1

| Campo | Valor |
|---|---|
| Tarea | FNC-DOM-005 |
| Estado | Review pending — amplía el seed v0 sin sustituirlo |
| ADR | ADR-004, ADR-005, ADR-006, ADR-023 |
| Gate | S1-READY |
| Owners requeridos | Data + Accounting |
| Revisores | Architecture, Security, Privacy |
| Modelo ejecutable | `docs/domain/lineage-model.json` |
| Validador | `python -m tools.lineage_model.validate` |
| Datos autorizados | Exclusivamente sintéticos |

`lineage-model.json` es la fuente estructurada **autoritativa**. Si este documento y el
modelo difieren, manda el modelo y la diferencia es un defecto que hay que corregir.

Esto es contrato de Fase 0. No define almacenamiento productivo, migraciones, parsers,
OCR real, conectores, interfaz ni IA externa. No aprueba releases, retención, región,
clasificación legal ni gates.

---

## 1. Qué identifica un origin locator

El seed v0 fijó el alcance y sigue vigente. Un origin locator identifica:

- artifact hash y `version_id`;
- página u hoja;
- fila, columna, celda o bounding box;
- tag XML o record de API;
- parser, OCR o modelo y su versión;
- receta, paso y overlay;
- campo canónico.

Lo que añade esta versión es que **no existe un locator universal opaco**: cada familia de
formato tiene su propia unión discriminada, con campos obligatorios, base ordinal y
validaciones de rango declaradas. §4 desarrolla las seis.

## 2. Invariantes

Los seis del seed se conservan literalmente:

- El localizador original es inmutable.
- Una corrección crea overlay o nueva versión.
- Todo campo publicado tiene al menos un camino completo a evidencia.
- Toda decisión de match, excepción, saldo e informe referencia versiones.
- Engine release fija semver, commit, hash, SBOM y `affects_results`.
- Reprocesar crea `dataset_version`; no reescribe históricos.

Esta versión añade siete que el seed daba por supuestos:

- **Company es la frontera.** Todo nodo y arista financiera es company-scoped; una arista entre companies distintas se rechaza.
- **Ningún valor raw viaja en aristas, logs o telemetría.** Solo digests y referencias.
- **El grafo es acíclico.** Un ciclo es un defecto, no una versión.
- **`derived_from`, `decided_using` e `included_in_snapshot` son operaciones distintas** y no intercambiables.
- **Fecha, monto, referencia y fingerprint no son identidad dura.** El linaje explica origen; no colapsa dos hechos distintos.
- **Un LLM no calcula dinero, confirma match, autoriza acceso ni cierra.** IA, OCR y modelos son productores versionados de propuesta o evidencia.
- **`unknown`, linaje incompleto o release no verificable bloquean** publicación y cierre.

---

## 3. Modelo de nodos y caminos

### 3.1 Tipos de nodo

| Nodo | Plano | Módulo | Mutabilidad |
|---|---|---|---|
| `artifact_version` | evidencia | ingestion | inmutable |
| `raw_locator` | evidencia | ingestion | inmutable |
| `extracted_field` | evidencia | clean | inmutable |
| `transformed_value` | evidencia | clean | versión inmutable |
| `source_record_field` | evidencia | clean | inmutable |
| `financial_fact_field` | financiero | finance | máquina de estados controlada |
| `decision` | financiero | reconciliation | append-only |
| `report_field` | analítico | reporting | versión inmutable |
| `close_snapshot_field` | financiero | close | inmutable |
| `reference_data_value` | control | sources | versión inmutable, no company-scoped |

Cada nodo lleva identidad inmutable, `company_id` cuando aplica, clasificación operativa,
etiquetas de dato personal, referencia de versión y digest SHA-256 del valor tipado. **El
valor raw no vive en el nodo.** Todo payload declara schema, versión de schema y tamaño
máximo: no se admite JSON libre.

### 3.2 Aristas

`lineage_edge` es append-only y transporta, como mínimo: company, origen y destino
tipados, operación, `processing_run_id`, `engine_release_id`, versión de esquema canónico,
receta y paso, overlay cuando aplica, versiones de regla, datos de referencia y modelo,
actor o workload, instante y referencia de auditoría.

Seis operaciones, con una distinción que importa:

| Operación | Significado | ¿Fluye el valor? |
|---|---|---|
| `derived_from` | el destino se calculó a partir del origen | sí |
| `decided_using` | una decisión consumió el origen como insumo sin derivar su valor | no |
| `included_in_snapshot` | el origen quedó sellado dentro de un snapshot | no |
| `overlay_applied` | un overlay aprobado cambió el valor efectivo | sí |
| `superseded_by` | el destino es una versión posterior | no |
| `redacted_from` | el destino es una minimización versionada | sí |

Confundir `derived_from` con `decided_using` haría creer que un match *calculó* un monto
cuando solo lo *consultó*. Son cosas distintas y el contrato las separa.

### 3.3 Caminos obligatorios

| Path | Secuencia | Si está incompleto |
|---|---|---|
| `PATH-SOURCE-RECORD` | artifact → locator → extracted → transformed → source_record | bloquea publicación |
| `PATH-FINANCIAL-FACT` | … + source_record → financial_fact | bloquea publicación |
| `PATH-DECISION` | … + financial_fact → decision | bloquea la decisión |
| `PATH-REPORT` | … + financial_fact → report_field | bloquea informe certificado |
| `PATH-CLOSE` | … + decision → close_snapshot_field | bloquea el cierre |

**La cobertura es del 100% y un promedio no la sustituye.** El validador rechaza
`average_coverage_allowed: true`: un 99,7% de campos con linaje significa que hay campos
publicados sin evidencia, y es precisamente ese 0,3% el que rompe una auditoría.

Las entidades del modelo canónico con `lineage_required: true` se derivan
**dinámicamente** de `canonical-model.json`. No se mantiene una lista paralela, porque una
lista paralela daría cobertura falsa en cuanto el modelo canónico cambiara.

Las decisiones de completitud, partidas conciliatorias y estados de conciliación se
materializan como nodos `decision`. Un estado `complete` sólo puede sobrevivir al
`COMMIT` si un trigger diferido verifica el camino exacto a sus datasets, saldos y
registros fuente. La base almacena nodos de baja cardinalidad y digests; las seis etapas
lógicas por columna permanecen en el plan de transformación versionado de ADR-024.

---

## 4. Origin locators tipados

Seis familias, cada una con campos obligatorios, base ordinal explícita y validaciones de
rango. Todas referencian `artifact_version_id` y `artifact_sha256`.

| Familia | Formatos | Base ordinal | Particularidad |
|---|---|---|---|
| `tabular_delimited` | CSV, TSV | 0 | encoding y dialecto versionados; byte span cuando existe |
| `spreadsheet` | XLSX | 1 | celda A1 coherente con fila y columna; **macro nunca se ejecuta** |
| `document_visual` | PDF nativo, PDF escaneado, imagen | 1 | sistema y unidad de coordenadas declarados; incertidumbre visible |
| `structured_markup` | XML, UBL/DIAN | 1 | namespace URI y ordinal por elemento repetido; **XPath del usuario nunca se ejecuta** |
| `record_stream` | OFX, MT940, camt.053, API | 0 | ordinal del artefacto recibido o handle estable, más versión del proveedor |
| `unknown_format` | no reconocido | — | **produce `review_required`, jamás un locator fabricado** |

Reglas transversales:

- El locator es inmutable.
- Fuera de rango produce `invalid`.
- La ambigüedad produce `review_required`.
- Un locator fabricado no es una opción: la incertidumbre se declara, no se rellena.
- Todo tipo declara su límite máximo de tamaño.

El valor mostrado y la fórmula de una celda se conservan como **metadatos con digest**,
nunca como algo ejecutable.

---

## 5. Overlays no destructivos

`field_overlay` es append-only y transporta valor tipado o una acción explícita —
`set_typed_value`, `redact_value`, `mark_unknown` — **nunca código arbitrario**.

Campos obligatorios: company, dataset, nodo y campo destino, versión base,
`expected_base_digest` y tipo esperado, acción y valor nuevo, motivo estructurado más
comentario acotado, actor, `authorization_version`, instante, versiones de engine, schema
y receta, clase de riesgo del campo, estado de aprobación, referencia de auditoría,
secuencia y overlay que revierte o sustituye.

### 5.1 Concurrencia y orden

- **Concurrencia optimista.** Un overlay contra una base stale produce `conflict` y no se aplica.
- **El reloj no ordena nada.** El orden efectivo es `(base_version_ref, sequence, overlay_id)`. No hay «last write wins».
- **Determinismo.** La misma cadena produce siempre el mismo valor efectivo, sea cual sea el orden de llegada.

### 5.2 Reversibilidad e inmutabilidad

- El **undo es otro overlay**, no una edición ni un borrado del anterior.
- Raw, extracción y `artifact_version` **no cambian nunca**.
- El **schema drift** invalida la aplicación silenciosa y exige nueva versión y revisión.
- Export y reprocess **declaran el conjunto ordenado exacto de overlays** aplicados, con su digest.

### 5.3 Segregación de funciones

Ocho campos son de clase crítica: `amount`, `currency`, `direction`,
`financial_account_identifier`, `tax_identity`, `accounting_date`, `posting_date` y
`value_date`. Un overlay sobre cualquiera de ellos **exige revisión independiente antes de
alimentar una decisión**: el autor no puede aprobar su propia corrección.

Solo el estado `applied` alimenta uso autoritativo. `draft`, `pending_review`, `rejected`,
`conflicted` y `reverted` quedan bloqueados para publicación, match, cierre e informe
certificado.

### 5.4 Qué debe explicar la interfaz

Esto no define UI; define lo que la UI tendrá que mostrar: valor original, valor efectivo,
diferencia, autor, motivo, estado de aprobación, instante y posición en la cadena.

---

## 6. Engine release y reproducibilidad

`engine_release` pertenece al módulo `platform`. El manifiesto es inmutable una vez
aprobado e incluye: ID y semver, commit fuente verificable y estado de árbol limpio,
SHA-256 de cada artefacto ejecutable, digest y formato de SBOM, digest del lockfile,
referencia de provenance, compatibilidad de esquema canónico, componentes incluidos —
parsers, OCR, modelos, reglas — con sus digests, clasificación, attestation, identidad del
builder, timestamp y estado.

### 6.1 Clasificación

| Clase | Exige | Si no lo demuestra |
|---|---|---|
| `affects_results` | corpus adjudicado, diff de resultados y revisión independiente | no se aprueba |
| `neutral` | prueba de equivalencia byte-for-byte y scope declarado | **se reclasifica como `affects_results`** |

Una release neutral que no demuestra equivalencia no es neutral: es una release cuyo
efecto nadie midió.

### 6.2 Aprobación y revocación

- La autoridad de aprobación es un **owner humano de Platform**. Un agente no puede autootorgársela.
- Una release **revocada no desaparece**: sigue siendo referenciable para explicar históricos, pero no produce runs nuevos.
- Los snapshots existentes conservan su referencia a la release revocada.
- Una release no verificable **bloquea publicación y cierre**.

### 6.3 Reproduction manifest

Fija entrada y versiones: artefacto y hash, dataset, plantilla de mapping, receta,
overlays ordenados con digest del conjunto, datos de referencia, parsers, modelos, reglas,
engine release, esquema canónico, locale, timezone, configuración determinista y semilla.

- **`latest`, `main`, `head`, `stable` y `current` están prohibidos.**
- La `reproduction_key` es SHA-256 sobre JSON canónico de la entrada, excluyendo los digests de salida: identifica **qué se pidió**, para poder comparar contra **qué salió**.
- El mismo manifest produce los mismos bytes canónicos **o falla explícitamente** con estado `not_reproducible`.
- Si un proveedor externo no ofrece versión fijable, **no se promete reproducibilidad**.

---

## 7. Reprocesamiento, diffs e históricos

- Un reprocess **siempre** crea `processing_run` y `dataset_version` nuevos.
- Registra `supersedes` **sin borrar** la versión anterior ni sus aristas.
- Calcula diff tipado por campo, registro y decisión, con delta exacto cuando hay dinero.
- Propaga impact analysis a hechos, matches, assessments, saldos, informes y snapshots.
- Un snapshot cerrado **conserva su release y su version set originales** y no lo muta un reprocess.
- Reabrir o republicar crea **revisión N+1** con motivo, aprobación y `authorization_version`; **no cambia N**.
- Si falta un binario, una release o un input requerido, el estado es `not_reproducible` y bloquea una afirmación exacta. **Nunca se sustituye por `latest`.**

### 7.1 El linaje no es dedupe

Compartir un locator **no implica** ser el mismo hecho. Dos movimientos legítimos
idénticos —mismo día, mismo monto, misma referencia— permanecen separados: es el caso
`TST-DED-002` de FNC-DOM-004 y el contrato de linaje lo preserva explícitamente. El linaje
explica de dónde viene un valor; no decide si dos valores son la misma cosa.

---

## 8. Eje de privacidad: mecanismo, no taxonomía

`DR-PRV-001` sigue en `Proposed`. Este contrato define **cómo se propaga** el segundo eje,
no qué contiene.

- `operational_classification` y `personal_data_tags` son **campos distintos**. Que un dato sea `internal` no significa que no sea personal.
- Los tags llevan `catalog_version` y estado `pending` o `approved`; la presencia es `none`, `possible`, `confirmed` o `unknown`, con `unknown` por defecto.
- **El contenido de la taxonomía lo definen Privacy y Legal**, no este documento ni un agente.
- Una transformación **no puede bajar ni eliminar tags** sin regla de minimización versionada, evidencia de redacción y aprobación. No hay degradación silenciosa.
- Ambos ejes viajan por `lineage_edge`, `field_overlay`, manifiesto de export, registro de IA, delete ledger, informes y snapshots.
- Mientras el estado sea `unknown` y la finalidad exija valoración personal, **el egreso externo queda bloqueado**.

---

## 9. Retención, tombstones y borrado

El linaje se vincula a las políticas `L-01-DERIVED`, `L-01-FINANCIAL`,
`L-01-AUDITABLE-DECISION`, `L-01-AUDIT`, `L-01-DELETE-LEDGER` y `L-01-BACKUP` del mapa de
privacidad. **Ninguna duración numérica se declara aquí**: L-01 pertenece a Legal y el
validador rechaza cualquier plazo escrito en este contrato.

Regla que conviene leer despacio: **el linaje no es excusa para conservar payload personal
eliminado**. Cuando un tombstone suprime un valor, el linaje sobrevive como referencia
minimizada y segregada más digest — suficiente para explicar que existió una derivación,
insuficiente para reconstruir el dato. El restore reaplica tombstones antes de reabrir el
servicio.

---

## 10. Verificación

```bash
python -m tools.lineage_model.validate
python -m unittest tools.lineage_model.test_validate -v
```

El validador carga en modo read-only `canonical-model.json`, `module-boundaries.json`,
`idempotency-dedupe.json`, `privacy-map.json`, `dfd-flows.json` y `threat-model.json`, y comprueba: cabecera y techos de fase,
tipos de nodo y su ownership contra las fronteras de módulos, contrato de aristas, los
cinco caminos obligatorios con cobertura del 100%, las seis familias de locator,
overlays y su máquina de estados, SoD de campos críticos, manifiesto de engine release,
reproducibilidad sin `latest`, reprocesamiento e históricos, propagación de los dos ejes
de clasificación, referencias a PA y L-01 del mapa de privacidad, vínculo de `C-LINEAGE`
con publicación/cierre y los riesgos TM-007, TM-008 y TM-015, sincronía dinámica con
las entidades `lineage_required` del modelo canónico, y que ningún gate ni decisión abierta
haya sido cerrado por un agente.

Además expone tres funciones puras probadas: `validate_graph` sobre un grafo sintético,
`apply_overlay_chain` determinista y `reproduction_key` por JSON canónico más SHA-256.

## 11. Decisiones abiertas

| ID | Pregunta | Owner |
|---|---|---|
| `UD-DR-PRV-001` | Resuelta por IMP-017: sensibilidad y categoría de dato personal son ejes separados; aplicabilidad Legal sigue antes de DRG-00 | Privacy |
| `UD-DR-LEG-001` | Reloj y orden de retención de linaje frente a backups y tombstones | Legal |
| `UD-RELEASE-APPROVAL` | Resuelta por IMP-017: humano Platform, evidencia reproducible y revisión independiente Security/QA | Platform |
| `UD-LOCATOR-STORAGE` | Resuelta por IMP-017 y ADR-024: plan compartido, localizador exacto y overrides append-only | Architecture |
| `UD-EXTERNAL-MODEL-PINNING` | Qué hacer cuando un proveedor externo no ofrece versión fijable | Architecture |

Ninguna se resuelve aquí. Aprobar este documento no supera S1-READY ni DRG-00.

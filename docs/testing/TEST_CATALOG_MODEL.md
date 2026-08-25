# Catálogo de pruebas ejecutable y reconciliación de cobertura

| Campo | Valor |
|---|---|
| Tarea | FNC-QA-004 |
| Estado | Review pending |
| Gate | S1-READY |
| Owners requeridos | QA |
| Revisores | Architecture, Accounting, Security |
| Modelo autoritativo | `docs/testing/test-catalog-model.json` |
| CLI | `python -m tools.test_catalog.cli` |
| Datos autorizados | Exclusivamente sintéticos |

Este modelo **no sustituye** a `TEST_CATALOG.md` ni lo edita nunca. Lo lee como una fuente
más y produce una propuesta de reconciliación para una decisión humana.

---

## 1. El problema: tres conjuntos que no son el mismo

La auditoría encontró tres poblaciones distintas de identificadores mezcladas en una sola
conversación:

1. **Requeridos por contratos ejecutables** — un `required_tests` en un modelo JSON.
2. **Documentados en el catálogo** — una fila de `TEST_CATALOG.md`.
3. **Materializados** — un nombre de test que ejecuta algo.

Un ID contractual ausente del catálogo es **drift de trazabilidad**: alguien declaró una
prueba obligatoria y la documentación no lo sabe. Un ID del catálogo sin contrato puede ser
una **especificación runtime planeada** perfectamente legítima. Contarlos juntos produce un
número grande y sin significado; el modelo los separa por diseño.

---

## 2. Extractores explícitos, no una regex global

No hay una búsqueda de `TST-` que se llame «definición». Hay **diez extractores**, cada uno
con su versión, la forma exacta que lee y la clase de fuente que produce:

| Extractor | Lee | Clase |
|---|---|---|
| `json_required_tests_objects` | `$.required_tests[]` con `{id, scenario}` | `contract_definition` |
| `json_required_tests_strings` | `$.required_tests[]` como cadenas | `contract_definition` |
| `json_required_test_scenarios` | `$.required_test_scenarios[]` | `contract_definition` |
| `json_strategy_test_ids` | `$.risk_control_matrix[].test_ids[]` | `reference` |
| `json_harness_test_refs` | `$.cases[].test_refs[]` | `reference` |
| `json_mutation_test_refs` | `$.mutations[].test_refs[]` | `reference` |
| `markdown_catalog_row` | fila `\| TST-… \| … \| … \|` | `catalog_row` |
| `markdown_narrative_mention` | cualquier `TST-` en prosa | `mention` |
| `python_test_method_name` | `def test_…_TST_XXX_NNN_…` | `implementation` |
| `javascript_test_name` | `test('TST-XXX-NNN …')` en `.mjs` | `implementation` |

`javascript_test_name` existe porque ignorarlo convertiría implementaciones reales del spike
en huecos inventados. `json_mutation_test_refs` se añadió cuando FNC-QA-005 introdujo un
contrato que ancla sus referencias en `mutations[]` y no en `cases[]`: sin él, un contrato
nuevo y elegible habría quedado invisible y el inventario habría parecido completo justo
donde no lo estaba. **Un contrato JSON nuevo bajo `docs/` entra automáticamente** por los
extractores de contrato: no hay una lista de ficheros que haya que recordar actualizar.

### Precedencia de clases

`contract_definition` › `catalog_row` › `implementation` › `reference` › `mention`

Una mención en prosa **nunca** cuenta como definición ni como implementación. Un comentario
tampoco. La misma ID en varias fuentes compatibles **no** es un duplicado: es procedencia
múltiple, y se conserva entera.

---

## 3. Rangos narrativos

`TST-CON-001..015` es **un ancla de mención**, no quince pruebas. Expandir un rango
narrativo inventaría cobertura que nadie escribió, así que el modelo declara
`expand_ranges: false` y el validador rechaza lo contrario. El inventario reporta los
rangos encontrados aparte, para que sean visibles sin contarlos.

---

## 4. Estados

`contract_required` · `catalog_planned` · `implemented` · `evidenced` ·
`waived_pending_human` · `orphan` · `conflict`

**Huérfano** es todo identificador sin clase de definición — incluido un test implementado
que ningún contrato exige. Un test que nadie pidió esconde la pregunta de por qué se
escribió.

---

## 5. Hallazgos, severidad y owner

| Hallazgo | Severidad | Clasificación | Owner |
|---|---|---|---|
| `TCM-ID-MALFORMED` | critical | integrity_error | QA |
| `TCM-CONTRACT-NOT-IN-CATALOG` | high | **traceability_drift** | QA |
| `TCM-DEFINITION-CONFLICT` | high | integrity_error | Architecture |
| `TCM-NAMESPACE-UNKNOWN` | high | integrity_error | QA |
| `TCM-CONTRACT-NOT-IMPLEMENTED` | medium | planned_backlog | QA |
| `TCM-ORPHAN` | medium | hygiene | QA |
| `TCM-CATALOG-PLANNED` | informational | **planned_backlog** | QA |

Bloquean `critical` y `high`. Los medios e informativos son backlog declarado y **no** se
cuentan como drift.

Sobre `TCM-DEFINITION-CONFLICT`: la divergencia de texto entre dos contratos es
mecánicamente detectable, pero **decidir cuál es autoritativo es una adjudicación humana**.
El validador señala; no infiere.

---

## 6. `model valid` no es `repository clean`

Son dos hechos distintos y el CLI los reporta por separado:

```json
{"model_valid": true, "repository_reconciliation_findings": 113, "ok": false}
```

`validate` sale distinto de cero cuando hay drift bloqueante, **sin que eso signifique que
el modelo sea inválido**. Rebajar la política para forzar verde sería exactamente el fallo
que este modelo existe para impedir.

---

## 7. CLI

```bash
python -m tools.test_catalog.cli discover
python -m tools.test_catalog.cli validate
python -m tools.test_catalog.cli report
python -m tools.test_catalog.cli project --format json
```

- `discover` — inventario estable, ordenado, con toda la procedencia.
- `validate` — validez del modelo **más** reconciliación del repositorio.
- `report` — conteos por estado, hallazgo, severidad, owner y gate. Sin nota global: un porcentaje agregado ocultaría justo el hallazgo crítico.
- `project` — propuesta machine-readable de adiciones y revisiones. **Nunca escribe `TEST_CATALOG.md`**, y hay prueba que comprueba el byte a byte del fichero tras ejecutarlo.

Salida UTF-8 por stdout, errores por stderr, orden determinista. `--root` se acepta solo si
resuelve a un directorio existente, sin `..` y sin ser un symlink.

---

## 8. Estado actual del repositorio

Medido sobre 286 ficheros y 96 identificadores:

| Estado | Cantidad |
|---|---:|
| `contract_required` | 81 |
| `implemented` | 30 |
| `catalog_planned` | 13 |
| `evidenced` | 6 |
| `orphan` | 2 |
| `conflict` | 1 |

Y los hallazgos, separados por naturaleza:

- **45 drift de trazabilidad** (`TCM-CONTRACT-NOT-IN-CATALOG`).
- **12 backlog planeado** (`TCM-CATALOG-PLANNED`) — no es drift.
- **52 contratos sin implementación** (`TCM-CONTRACT-NOT-IMPLEMENTED`) — backlog.
- **1 conflicto de definición**: `TST-DED-002` está definido en `idempotency-dedupe.json` y en `lineage-model.json` con texto distinto.
- **1 namespace desconocido**: `TST-QS-001`, citado en `TRACEABILITY.md`.
- **2 huérfanos**: `TST-DB-001` y `TST-QS-001`, mencionados en prosa sin definición.

---

## 9. Límites honestos

1. **Un run verde prueba que el inventario es coherente, no que las pruebas existan.**
2. **Un ID en el catálogo no demuestra que exista código que lo ejecute.**
3. **Un ID implementado no demuestra que la prueba sea correcta ni suficiente.**
4. **La reconciliación no acredita cobertura de riesgo**: eso lo declara `test-strategy.json`.
5. **Este modelo no edita `TEST_CATALOG.md` y no cierra ninguna decisión humana.**

## 10. Decisiones abiertas

| ID | Pregunta | Owner |
|---|---|---|
| `UD-QA-CATALOG-OWNER` | Resuelta por IMP-017: QA al cambiar contratos y antes de release; revisa Integration Steward | QA |
| `UD-QA-CATALOG-FORMAT` | Resuelta por IMP-017: JSON autoritativo y Markdown como proyección humana | QA |
| `UD-QA-RUNTIME-BACKLOG` | Qué IDs planeados pasan a requisito contractual y cuándo | QA |

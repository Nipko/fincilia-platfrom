# Handoff — FNC-QA-004: catálogo de pruebas ejecutable y reconciliación

| Campo | Valor |
|---|---|
| Tarea | FNC-QA-004 |
| Estado | `REVIEW_PENDING` |
| Base declarada | `6e23c04` — **entregada por el Integration Steward, no verificada** |
| Verificación de la base | No se usó Git en ninguna forma: sin `status`, `diff`, `log`, `show`, `add`, `commit`, `checkout` ni lectura del índice |
| `integration_sha` | `pending_integration_steward` |
| `quality_gate_on_git_index` | `pending_integration_steward` |
| Owner | QA |
| Revisores independientes requeridos | Architecture, Security, Accounting |
| Gate | S1-READY — `not_met` |

---

## 1. Qué problema resuelve

La auditoría mezclaba tres poblaciones distintas de identificadores en una sola conversación:
los exigidos por contratos ejecutables, los documentados en `TEST_CATALOG.md` y los
materializados por tests. Sumarlas produce un número grande y sin significado.

El modelo las separa por diseño. Un ID contractual ausente del catálogo es **drift de
trazabilidad**. Un ID del catálogo sin contrato puede ser una **especificación runtime
planeada** perfectamente legítima. No son lo mismo y nunca se suman.

---

## 2. Rutas creadas o modificadas

| Ruta | Acción |
|---|---|
| `docs/testing/test-catalog-model.json` | creada — modelo autoritativo |
| `docs/testing/TEST_CATALOG_MODEL.md` | creada — documentación |
| `tools/test_catalog/__init__.py` | creada |
| `tools/test_catalog/extractors.py` | creada — 10 extractores explícitos |
| `tools/test_catalog/reconcile.py` | creada — descubrimiento, clasificación, reconciliación |
| `tools/test_catalog/cli.py` | creada — `discover`/`validate`/`report`/`project` |
| `tools/test_catalog/test_validate.py` | creada — 35 pruebas |
| `docs/implementation/handoffs/FNC-QA-004.md` | este documento |

**No** se tocó `TEST_CATALOG.md`, CI, `CURRENT_PHASE.md`, backlog, trazabilidad, grafo de
trabajo, ADR, tareas ni ningún contrato o herramienta ajeno. Todas las rutas reservadas por
FNC-QA-004 quedan liberadas.

---

## 3. Contratos e invariantes implementadas

- **Diez extractores explícitos**, cada uno con versión, forma exacta que lee y clase de
  fuente que produce. No existe una regex global de `TST-` que se llame definición.
- **Precedencia de clases**: `contract_definition` › `catalog_row` › `implementation` ›
  `reference` › `mention`. Una mención en prosa nunca es definición ni implementación.
- **Provenance completa**: ruta, localizador estable, digest SHA-256 y extractor con versión.
  La misma ID en fuentes compatibles es procedencia múltiple, no duplicado; definiciones
  incompatibles sí son conflicto.
- **Rangos narrativos no se expanden** (`expand_ranges: false`). `TST-CON-001..015` es un
  ancla de mención, no quince pruebas.
- **Huérfano** es todo identificador sin clase de definición, incluido un test implementado
  que ningún contrato exige.
- **Severidad y owner por hallazgo**; bloquean `critical` y `high`.
- **`project` nunca escribe el catálogo**, y hay prueba que compara el fichero byte a byte
  después de ejecutarlo.
- **`--root` se valida**: debe existir, no contener `..` y no ser un symlink externo.

Las 20 invariantes negativas del encargo tienen prueba que parte de una entrada válida y la
degrada exactamente una vez, más tres metamórficas.

---

## 4. Comandos ejecutados y resultado

| Comando | Exit | Resultado |
|---|---:|---|
| `python -m tools.test_catalog.cli discover` | 0 | 286 ficheros, 96 identificadores |
| `python -m tools.test_catalog.cli validate` | **1** | `model_valid: true`, 113 hallazgos de reconciliación |
| `python -m tools.test_catalog.cli report` | 0 | conteos por estado, hallazgo, severidad, owner y gate |
| `python -m tools.test_catalog.cli project --format json` | 0 | 45 adiciones propuestas, 4 revisiones humanas, 12 backlog planeado |
| `python -m unittest tools.test_catalog.test_validate` | 0 | **35 pruebas, OK** |

### `model valid` no es `repository clean`

Son dos hechos distintos y el CLI los reporta por separado:

```json
{"model_valid": true, "repository_reconciliation_findings": 113, "ok": false}
```

`validate` sale con exit 1 **por el drift preexistente que el modelo existe para medir**, no
porque el modelo sea inválido. La verificación estructural del modelo da PASS. No se rebajó
ninguna política para forzar verde: hacerlo habría sido exactamente el fallo que este modelo
está para impedir.

---

## 5. Estado medido del repositorio

| Estado | Cantidad |
|---|---:|
| `contract_required` | 81 |
| `implemented` | 30 |
| `catalog_planned` | 13 |
| `evidenced` | 6 |
| `orphan` | 2 |
| `conflict` | 1 |

| Hallazgo | Cantidad | Naturaleza | Severidad | Owner |
|---|---:|---|---|---|
| `TCM-CONTRACT-NOT-IN-CATALOG` | 45 | **drift de trazabilidad** | high | QA |
| `TCM-CONTRACT-NOT-IMPLEMENTED` | 52 | backlog planeado | medium | QA |
| `TCM-CATALOG-PLANNED` | 12 | backlog planeado | informational | QA |
| `TCM-ORPHAN` | 2 | higiene | medium | QA |
| `TCM-DEFINITION-CONFLICT` | 1 | error de integridad | high | Architecture |
| `TCM-NAMESPACE-UNKNOWN` | 1 | error de integridad | high | QA |

Los 45 de drift y los 12 de backlog planeado **no se suman**. Son poblaciones distintas.

---

## 6. Hallazgos fuera de scope — reportados, no corregidos

| ID | Ruta | Impacto | Owner |
|---|---|---|---|
| `TST-DED-002` | `docs/domain/idempotency-dedupe.json` y `docs/domain/lineage-model.json` | La misma ID está definida en dos contratos con texto distinto. La divergencia es mecánicamente detectable; **decidir cuál es autoritativo es una adjudicación humana**. | Architecture |
| `TST-QS-001` | `docs/implementation/TRACEABILITY.md` | Namespace `QS` desconocido y sin definición en ningún contrato. | QA |
| `TST-DB-001` | prosa | Mencionado sin definición: huérfano. | QA |
| `FNC-PLT-006` | `docs/implementation/tasks/FNC-PLT-006.md` | `python -m unittest tools.work_graph.test_validate` falla con `META-TASK-ORPHAN`: la tarea existe y **no está en el backlog**. Preexistente y ajeno a estas rutas; no se tocó. | Integration Steward |

---

## 7. Cambio de alcance justificado durante la ejecución

Se añadió el extractor **`json_mutation_test_refs`** (`$.mutations[].test_refs[]`) y el
namespace **`MUT`** al modelo, ambos dentro de rutas reservadas por FNC-QA-004.

Motivo: FNC-QA-005 introdujo `docs/testing/mutation-harness.json`, un contrato elegible que
ancla sus referencias en `mutations[]` y no en `cases[]`. Sin el extractor habría quedado
invisible y el inventario habría parecido completo justo donde no lo estaba — que es
precisamente la invariante negativa 14 del encargo. Se añadió prueba para ambos casos
(`test_neg_14b`, `test_neg_14c`).

---

## 8. Riesgos, rollback y compatibilidad

- **Riesgo**: `validate` sale con exit 1 mientras exista drift. Si CI lo ejecutara como
  bloqueante hoy, fallaría. La decisión de cuándo activarlo es humana (`UD-QA-CATALOG-OWNER`).
- **Riesgo**: los extractores leen formas concretas. Un contrato futuro con una forma nueva
  necesitará su extractor; `test_neg_14c` obliga a que modelo, código y aplicabilidad
  declaren el mismo conjunto, de modo que un extractor añadido a medias falla en pruebas.
- **Rollback**: eliminar `tools/test_catalog/`, `docs/testing/test-catalog-model.json` y
  `docs/testing/TEST_CATALOG_MODEL.md`. Ningún otro fichero depende de ellos y `TEST_CATALOG.md`
  nunca fue modificado, así que el rollback es total y sin residuo.
- **Compatibilidad**: no altera contratos existentes. Solo los lee.

---

## 9. Decisiones abiertas

| ID | Pregunta | Owner |
|---|---|---|
| `UD-QA-CATALOG-OWNER` | Quién reconcilia el catálogo y con qué cadencia | QA |
| `UD-QA-CATALOG-FORMAT` | Si el catálogo debe pasar a formato estructurado | QA |
| `UD-QA-RUNTIME-BACKLOG` | Qué IDs planeados pasan a requisito contractual y cuándo | QA |

Ninguna se cierra aquí. No se aceptó ningún gate, ADR, riesgo residual ni decisión humana.

---

## 10. Pasos exactos para el Integration Steward

1. **Indexar** las rutas de la sección 2.
2. **Ejecutar el quality gate sobre el índice Git.** No se ejecutó aquí y no se declara
   exitoso: los ficheros son nuevos y el gate opera sobre el índice.
3. **CI**: decidir si `test_catalog validate` entra como informativo o bloqueante. Hoy sale 1
   por drift preexistente.
4. **Catálogo**: revisar `project --format json` y aplicar a mano las 45 adiciones propuestas
   y las 4 revisiones humanas. La herramienta no escribe `TEST_CATALOG.md` por diseño.
5. **Adjudicar** `TST-DED-002` (conflicto de definición) y `TST-QS-001` (namespace desconocido).
6. **`CURRENT_PHASE.md`, backlog, trazabilidad y grafo de trabajo**: actualizar según proceda.
   No se tocaron.
7. **Liberar reservas** de FNC-QA-004.
8. **Revisar aparte** el fallo preexistente de `tools.work_graph` (`FNC-PLT-006`).

Estado final: **`REVIEW_PENDING`**. No se declara aceptación, integración, head SHA, CI
remoto ni revisión humana inexistentes.

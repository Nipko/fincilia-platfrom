# Handoff — FNC-QA-005: arnés de mutaciones ejecutable

| Campo | Valor |
|---|---|
| Tarea | FNC-QA-005 |
| Estado | `REVIEW_PENDING` |
| Base declarada | `6e23c04` — **entregada por el Integration Steward, no verificada** |
| Verificación de la base | No se usó Git en ninguna forma: sin `status`, `diff`, `log`, `show`, `add`, `commit`, `checkout` ni lectura del índice |
| `integration_sha` | `pending_integration_steward` |
| `quality_gate_on_git_index` | `pending_integration_steward` |
| Owner | QA |
| Revisores independientes requeridos | Security, Architecture, Accounting |
| Gates | S1-READY, DRG-00, DRG-01, L-02 — todos `not_met` |

---

## 1. Qué demuestra

Que 61 de 63 reglas críticas de nueve contratos ejecutables **reaccionan** cuando alguien las
debilita, y que las dos que no reaccionan son fallos reales, localizados y con owner.

Una suite en verde demuestra que las pruebas pasan; no demuestra que los validadores muerdan.
Un validador que devuelve `ok: true` pase lo que pase también aprueba todos sus tests. Un
mutante que sobrevive es un test que falta.

---

## 2. Rutas creadas o modificadas

| Ruta | Acción |
|---|---|
| `docs/testing/mutation-harness.json` | creada — registro autoritativo, 63 mutaciones |
| `docs/testing/MUTATION_HARNESS.md` | creada — documentación |
| `tools/mutation_harness/__init__.py` | creada |
| `tools/mutation_harness/operators.py` | creada — 7 operadores declarativos |
| `tools/mutation_harness/registry.py` | creada — validación estricta del registro |
| `tools/mutation_harness/runner.py` | creada — ejecución aislada y clasificación |
| `tools/mutation_harness/cli.py` | creada — `list`/`verify`/`run`/`report` |
| `tools/mutation_harness/test_harness.py` | creada — 94 pruebas |
| `tests/golden/mutations/synthetic_contract.json` | creada — fixture |
| `tests/golden/mutations/synthetic_evidence.json` | creada — fixture |
| `tests/golden/mutations/synthetic_validator.py` | creada — validador de laboratorio |
| `tests/golden/mutations/MANIFEST.json` | creada — inventario con digests |
| `docs/implementation/handoffs/FNC-QA-005.md` | este documento |

**Ningún contrato, herramienta, test ni fixture ajeno fue modificado.** FNC-QA-002 y
FNC-QA-003 se consumieron solo como contratos ya integrados. Todas las rutas reservadas por
FNC-QA-005 quedan liberadas.

---

## 3. Contratos e invariantes implementadas

- **Línea base obligatoria**: cada caso ejecuta el validador sobre la copia *sin mutar* antes
  de mutar. Si no sale limpia, el caso es `invalid`. Sin esto, un kill sería ambiguo.
- **Operadores declarativos**: siete, con parámetros exactos y JSON Pointer. Sin `eval`, sin
  snippets, sin regex libre, sin shell, sin comandos tomados del registro. Cuatro exigen
  `expected_current`, para que una mutación que dejó de aplicarse se note en vez de silenciarse.
- **Aislamiento**: directorio temporal por caso, solo inputs allowlisted, `argv` en lista,
  `shell=False`, `cwd` validado, entorno mínimo por allowlist, timeout y límite de salida.
- **Cinco resultados**, no dos: `killed`, `survived`, `invalid`, `equivalent_pending_review`,
  `error`. Timeout, excepción, truncamiento y exit no-cero *por otro motivo* nunca son kill.
  `equivalent_pending_review` no se marca solo: es adjudicación humana.
- **Independencia**: dos mutaciones independientes no pueden esperar el mismo código sobre el
  mismo validador (`MH-REDUNDANT-CONTROL`). Cuando varias banderas son un solo control, se
  declaran como grupo de equivalencia y cuentan como uno.
- **Árbol fuente intacto**: se recalculan los digests de todas las rutas vigiladas después de
  cada run y el resultado lo reporta.
- **Digest determinista**: cubre registro, mutación, target, expectativa, exit codes y
  códigos observados; excluye duración, hostname, timestamp y versión parche del intérprete.
- **Manifiesto limpio**: sin payloads, sin entorno, sin secretos.

Las 20 invariantes negativas del encargo tienen prueba negativa.

---

## 4. Comandos ejecutados y resultado

| Comando | Exit | Resultado |
|---|---:|---|
| `python -m tools.mutation_harness.cli list` | 0 | 63 mutaciones, 4 gaps declarados |
| `python -m tools.mutation_harness.cli verify` | 0 | registro válido, 0 errores |
| `python -m tools.mutation_harness.cli run` | **1** | 61 `killed`, 2 `survived`, 0 sin resolver, árbol intacto |
| `python -m tools.mutation_harness.cli report` | **1** | por riesgo y control; `single_pass_score: null` |
| `python -m unittest tools.mutation_harness.test_harness` | 0 | **94 pruebas, OK** |
| `python -m tools.quality_strategy.validate` | 0 | sin errores |
| `python -m tools.golden_harness.cli verify` | 0 | sin errores |
| `python -m tools.golden_harness.cli run` | 0 | sin errores |
| `python -m unittest tools.quality_strategy.test_validate tools.golden_harness.test_harness` | 0 | OK |

`registry_digest` del run: `1bd90732bc83d26f77454fcc627a3abd42f9506eb73c8abac9c880ae6995f5b7`.
Dos ejecuciones consecutivas produjeron el mismo `deterministic_result_digest` en los 63 casos.

**`run` y `report` salen con exit 1 porque hay dos supervivientes reales**, no porque el
arnés esté averiado. Bajar su severidad para forzar verde sería el fallo exacto que este
arnés existe para detectar.

`tools.quality_gate.cli` **no** se ejecutó ni se declara exitoso: los ficheros son nuevos y
el gate opera sobre el índice Git.

---

## 5. Cobertura: 63 mutaciones, 9 validadores

`test-strategy.json` exige `minimum_mutants_per_validator: 5`; ninguno baja de 6.

| Validador | Mutaciones | Dominio exigido por el encargo |
|---|---:|---|
| `canonical_model` | 6 | company scope, Decimal/float, dirección |
| `completeness_model` | 6 | completitud, Unknown, cierre |
| `connector_model` | 7 | egress, datos prohibidos, credenciales |
| `event_model` | 7 | retry ownership, DLQ sin raw, autorización |
| `golden_harness` | 7 | alteración de input y digest, traversal |
| `idempotency_model` | 7 | dedupe sin composite UNIQUE peligroso |
| `lineage_model` | 9 | linaje, engine release, versiones flotantes, SoD |
| `privacy_model` | 7 | IA fail-closed, autoridad de almacén, borrado |
| `quality_strategy` | 7 | dominios protegidos, cobertura, aceptación humana |

Cada dominio pedido está cubierto por mutaciones concretas. Los códigos esperados se
derivaron **observando los validadores reales**, no adivinando, y quedaron fijados en el
registro: si un validador deja de emitirlos, la mutación sobrevive y el arnés lo dice.

---

## 6. Supervivientes: dos hallazgos reales, no corregidos

Ambos caen en herramientas ya integradas y fuera del alcance de FNC-QA-005. Se reportan; no
se tocan.

| Mutación | Validador | Hallazgo | Riesgo | Owner | Gate |
|---|---|---|---|---|---|
| `MUT-PRV-006` | `privacy_model` | Valida las rutas de evidencia por **existencia**, no por contención canónica: `docs/../docs/architecture/dfd-flows.json` se acepta sin observación. Dos grafías del mismo fichero hacen ambigua la contabilidad de digests. | TM-011 (high) | Security | S1-READY |
| `MUT-GHR-006` | `golden_harness` | `adjudication.runner_can_update_expected` se declara pero **nunca se comprueba**; solo `auto_update_expected_allowed` está aplicado. El registro puede quedar internamente contradictorio sin que nada lo señale. | TM-013 (high) | QA | S1-READY |

### Observación relacionada, deliberadamente no codificada

`privacy_model` también acepta una ruta de evidencia **absoluta del host** (por ejemplo
`C:/Windows/win.ini`) cuando ese fichero existe en la máquina. Es más grave que el caso
anterior, pero **no se declaró como mutación** porque su resultado depende del host:
sobreviviría en un portátil y moriría en CI. Una mutación no determinista no pertenece a un
registro adjudicado. Queda como hallazgo para el owner de `privacy_model` (Security,
S1-READY).

---

## 7. Gaps declarados: cobertura que no se inventó

| Riesgo | Por qué no es mutable desde un contrato | Owner | Gate | Bloquea |
|---|---|---|---|---|
| `TM-002` | Exige PostgreSQL real con RLS activo; en E0 no hay base de datos y mutar un JSON no prueba aislamiento de filas. | Backend | DRG-01 | sí |
| `TM-005` | Cadena de suministro y firma de artefactos se verifican en CI e infraestructura. Las mutaciones de `data_ceiling` cubren la declaración, no el perímetro. | Security | DRG-00 | sí |
| `TM-006` | El aislamiento de red y runtime del worker exige despliegue real. | Platform | DRG-01 | sí |
| `TM-010` | La superficie de IA está deshabilitada por contrato; solo se puede mutar la bandera global, no el comportamiento de un proveedor inexistente. | AI Platform | L-02 | sí |

Coherente con `test-strategy.json`. Ninguno se cierra aquí.

---

## 8. Fixtures sintéticos

`tests/golden/mutations/` contiene contrato, evidencia y validador sintéticos más
`MANIFEST.json` con el digest de cada fichero. Hay prueba de que todo fichero está
inventariado, de que cada digest coincide y de que ninguno contiene email, NIT, IP pública ni
`TODO` anónimo.

El validador sintético sabe portarse mal a propósito —aceptar todo, fallar por el motivo
equivocado, imprimir basura, pasarse del timeout, ensuciar la línea base— porque probar el
clasificador solo contra validadores que funcionan no demostraría que distingue un control
que muerde de un proceso que se cayó. Ese validador se ejecuta por ruta de script y **la
política del registro lo rechaza** (`MH-ARGV-MODULE`, `MH-MODULE-ALLOWLIST`); hay prueba de
ello, y por eso el laboratorio no pasa por `validate_registry`.

---

## 9. Hallazgos fuera de scope — reportados, no corregidos

| ID | Ruta | Impacto | Owner |
|---|---|---|---|
| Contención de rutas | `tools/privacy_model/validate.py` | Evidencia validada por existencia, no por contención. Ver §6. | Security |
| Política declarada sin aplicar | `tools/golden_harness/registry.py` | `runner_can_update_expected` no se comprueba. Ver §6. | QA |
| `FNC-PLT-006` | `docs/implementation/tasks/FNC-PLT-006.md` | `python -m unittest tools.work_graph.test_validate` falla con `META-TASK-ORPHAN`: la tarea existe y no está en el backlog. Preexistente y ajeno a estas rutas. | Integration Steward |

---

## 10. Riesgos, rollback y compatibilidad

- **Riesgo**: `run` y `report` salen con exit 1 mientras existan los dos supervivientes. Si CI
  los ejecuta como bloqueantes, fallarán hasta que Security y QA adjudiquen. Es el
  comportamiento previsto.
- **Riesgo**: el registro fija digests de los contratos objetivo. Cualquier cambio legítimo en
  un contrato hará fallar `verify` con `MH-TARGET-HASH` hasta re-adjudicar. Es deliberado:
  una mutación sobre un contrato distinto del adjudicado no prueba lo mismo.
- **Riesgo**: coste. 63 mutaciones son 126 subprocesos; el run completo tarda alrededor de un
  minuto en esta máquina. La cadencia en CI es decisión humana (`UD-QA-MUT-BUDGET`).
- **Rollback**: eliminar `tools/mutation_harness/`, `tests/golden/mutations/`,
  `docs/testing/mutation-harness.json` y `docs/testing/MUTATION_HARNESS.md`. Nada más depende
  de ellos y ningún contrato ajeno fue modificado, así que el rollback es total.
- **Compatibilidad**: el arnés solo **lee** contratos y **copia** inputs. Nunca escribe en el
  árbol compartido, y hay prueba que lo comprueba por digest después de cada run.

---

## 11. Decisiones abiertas

| ID | Pregunta | Owner |
|---|---|---|
| `UD-QA-MUT-BUDGET` | Cadencia y presupuesto de ejecución en CI | QA |
| `UD-QA-MUT-SURVIVOR` | Quién adjudica un superviviente: arreglar el validador o aceptar el riesgo | QA |
| `UD-QA-MUT-EQUIVALENCE` | Criterio para declarar una mutación equivalente sin revisión caso a caso | Architecture |

No se aceptó ningún gate, ADR, riesgo residual ni decisión humana.

---

## 12. Pasos exactos para el Integration Steward

1. **Indexar** las rutas de la sección 2.
2. **Ejecutar el quality gate sobre el índice Git.** No se ejecutó aquí y no se declara
   exitoso.
3. **CI**: decidir si el arnés entra como lane propio y con qué cadencia. Hoy sale 1 por dos
   supervivientes reales.
4. **Adjudicar los dos supervivientes** con Security y QA: arreglar el validador o aceptar el
   riesgo por escrito. Mientras tanto siguen bloqueando S1-READY.
5. **Catálogo/proyección**: `TST-MUT-001` es nuevo y aparece como drift en la proyección de
   FNC-QA-004. Añadirlo a `TEST_CATALOG.md` a mano.
6. **`CURRENT_PHASE.md`, backlog, trazabilidad y grafo de trabajo**: actualizar según proceda.
   No se tocaron.
7. **Liberar reservas** de FNC-QA-005.

Estado final: **`REVIEW_PENDING`**. No se declara aceptación, integración, head SHA, CI
remoto ni revisión humana inexistentes.

---

## 13. Compatibilidad conjunta QA-002 → QA-003 → QA-004 → QA-005

Los cuatro carriles encajan como una cadena, cada uno consumiendo al anterior sin editarlo:

| Carril | Aporta | Lo consume |
|---|---|---|
| **FNC-QA-002** — `test-strategy.json` | matriz riesgo↔control, dominios protegidos, `mutation_policy` con `minimum_mutants_per_validator: 5` | QA-004 lee sus `test_ids` como referencias; QA-005 cumple el mínimo y usa sus `TM-*` como `risk_refs` |
| **FNC-QA-003** — `golden-harness.json` | casos adjudicados, digests de input, autoridad humana de adjudicación | QA-004 lee sus `cases[].test_refs`; QA-005 lo trata como **validador objetivo**, con 7 mutaciones propias |
| **FNC-QA-004** — `test-catalog-model.json` | inventario y reconciliación contract↔catalog↔implementation | QA-005 declara `required_tests` y `test_refs` que QA-004 descubre y reconcilia |
| **FNC-QA-005** — `mutation-harness.json` | prueba de que los controles muerden | devuelve a QA-002 la evidencia que `mutation_policy` exige |

**Coherencia verificada, no supuesta:**

- Las 203 pruebas de los cuatro carriles se ejecutaron juntas y pasan
  (`tools.test_catalog.test_validate`, `tools.mutation_harness.test_harness`,
  `tools.quality_strategy.test_validate`, `tools.golden_harness.test_harness`).
- Las 686 pruebas de todas las herramientas del repositorio se ejecutaron juntas: pasan todas
  salvo el fallo preexistente y ajeno de `tools.work_graph` (§9).
- `mutation_policy.minimum_mutants_per_validator: 5` se comprueba en prueba
  (`test_cli_04`), de modo que el mínimo no puede degradarse en silencio.
- El registro de QA-005 no duplica listas de IDs ni de validadores: QA-004 los descubre
  dinámicamente y QA-005 los declara una sola vez con hash.

**Un acoplamiento que conviene conocer:** QA-005 fija el SHA-256 de nueve contratos. Cuando
QA-002 o QA-003 cambien legítimamente uno de ellos, `verify` fallará con `MH-TARGET-HASH`
hasta re-adjudicar la mutación. Es intencionado —una mutación sobre un contrato distinto del
adjudicado no prueba lo mismo— pero significa que el owner de un contrato tiene que avisar a
QA, y no al revés.

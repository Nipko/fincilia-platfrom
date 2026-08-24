# Arnés de mutaciones ejecutable

| Campo | Valor |
|---|---|
| Tarea | FNC-QA-005 |
| Estado | Review pending |
| Gates | S1-READY, DRG-00, DRG-01, L-02 (todos `not_met`) |
| Owner | QA |
| Revisores independientes | Security, Architecture, Accounting |
| Registro autoritativo | `docs/testing/mutation-harness.json` |
| CLI | `python -m tools.mutation_harness.cli` |
| Fixtures | `tests/golden/mutations/` — sintéticos e inventariados |
| Datos autorizados | Exclusivamente sintéticos. Cero red. |

---

## 1. Qué demuestra y qué no

Una suite en verde demuestra que las pruebas pasan. **No** demuestra que los validadores
muerdan: un validador que devuelve `ok: true` pase lo que pase también aprueba todos sus
tests. El arnés existe para responder una sola pregunta, contrato por contrato:

> Si alguien debilitara esta regla exacta, ¿alguien se daría cuenta?

Un mutante que sobrevive **es un test que falta**, no un dato curioso.

Lo que el arnés **no** hace, y no debe presentarse como si lo hiciera:

- No verifica infraestructura real: ni base de datos, ni RLS, ni red, ni despliegue.
- No sustituye pruebas de integración.
- No acepta salidas esperadas ni adjudica nada.
- No convierte una nota alta en seguridad ni en exactitud contable.

---

## 2. Por qué la línea base tiene que estar limpia

Cada caso ejecuta el validador **dos veces**: primero sobre la copia sin mutar, después
sobre la copia mutada. Si la primera ejecución no sale con exit `0`, el caso se marca
`invalid` y no se cuenta.

El motivo es exacto: si la línea base ya fallaba —porque falta un input, porque el contrato
venía roto, porque el módulo no importa— entonces el fallo posterior **no prueba nada sobre
la mutación**. Sin esta precondición, un directorio temporal mal armado produciría 68
«controles acreditados» y ni uno solo sería real.

---

## 3. Operadores: datos, nunca código

Siete operadores declarativos, con parámetros exactos y punteros JSON Pointer (RFC 6901):

| Operador | Qué hace | Para qué sirve |
|---|---|---|
| `delete_key` | borra exactamente una clave o elemento | desaparece una regla o un campo obligatorio |
| `replace_scalar` | sustituye un escalar exigiendo su valor actual | cambia un umbral, un estado o un techo |
| `flip_boolean` | invierte una bandera booleana | apaga autoridad, seguridad o SoD |
| `insert_element` | inserta un elemento en una posición | añade una clasificación prohibida |
| `reorder_list` | invierte una lista sin cambiar contenido | **control metamórfico** |
| `path_traversal_internal` | reescribe una ruta válida en forma no canónica con `..` | dos grafías del mismo fichero |
| `float_version_token` | degrada una versión exacta a `latest` | reproducibilidad rota |

No hay `eval`, ni snippets de Python, ni regex de reemplazo libre, ni shell, ni comandos
tomados del registro. Un registro capaz de describir código sería un ejecutor de código
disfrazado de configuración; el validador del registro rechaza cualquier parámetro que se
parezca a código.

`replace_scalar`, `flip_boolean`, `path_traversal_internal` y `float_version_token` exigen
`expected_current`. Mutar a ciegas produciría mutaciones que silenciosamente dejan de
aplicarse cuando el contrato cambia, y un caso que ya no muta **no puede matar nada**.

---

## 4. Aislamiento de la ejecución

1. Se verifica el registro completo —hashes, rutas, precondiciones— **antes** de ejecutar nada.
2. Se crea un directorio temporal propio por caso y se copian **solo** los inputs allowlisted.
3. Se ejecuta la línea base. Si no sale limpia, el caso es `invalid`.
4. Se aplica **exactamente una** mutación sobre la copia.
5. Se ejecuta el validador con lista `argv`, `shell=False`, `cwd` validado y entorno mínimo.
6. Timeout y límite de salida acotados; el truncamiento es fallo de evaluación, no un kill.
7. Al terminar se recalculan los digests del árbol fuente para demostrar que sigue intacto.

El entorno se construye por allowlist (`PATH`, `SYSTEMROOT`, `COMSPEC`, `TEMP`, `TMP`,
`LANG`, `LC_ALL`) más ajustes deterministas. **No** se heredan proxies, tokens ni
credenciales: un validador que pudiera salir a la red dejaría de ser una función pura de
sus inputs.

---

## 5. Clasificación: cinco resultados, no dos

| Resultado | Significa |
|---|---|
| `killed` | el validador falló con **los códigos exactos** declarados |
| `survived` | aceptó el contrato debilitado, o falló por otro motivo |
| `invalid` | la línea base venía sucia, o la mutación no pudo aplicarse |
| `equivalent_pending_review` | se sospecha equivalencia semántica: **revisión humana** |
| `error` | timeout, excepción, salida truncada o ilegible |

Tres decisiones deliberadas:

- **Un exit no-cero genérico no es un kill.** Si esperábamos `CMP-AUTO-MATCH` y el validador
  falla por `CMP-MONEY`, el control que creíamos tener no quedó acreditado. El caso cuenta
  como superviviente.
- **Un timeout o un truncamiento nunca son kill.** No se sabe qué pasó; fingir que sí es
  justo la clase de aritmética optimista que este arnés existe para impedir.
- **`equivalent_pending_review` no se marca solo.** Declarar una mutación equivalente es una
  adjudicación humana; automatizarla convertiría cada superviviente incómodo en una excusa.

---

## 6. Independencia y grupos de equivalencia

Dos mutaciones independientes **no pueden** esperar el mismo código de hallazgo sobre el
mismo validador: sería una regla contada dos veces, y la cobertura parecería el doble de lo
que es. El validador del registro lo rechaza con `MH-REDUNDANT-CONTROL`.

Cuando varias banderas expresan de verdad *un solo* control, se declaran como grupo:

| Grupo | Mutaciones | Control |
|---|---|---|
| `EQG-CON-EGRESS-PERIMETER` | `MUT-CON-001/002/003` | `CON-SECURITY` |
| `EQG-QS-PROTECTED-DOMAIN` | `MUT-QST-001/002` | `QS-PROTECTED-SKIP` |

Un grupo cuenta como **un** control, no como tres.

---

## 7. Cobertura actual

68 mutaciones sobre 9 validadores ya inyectables. `test-strategy.json` exige
`minimum_mutants_per_validator: 5`; ninguno baja de 6.

| Validador | Mutaciones | Dominio atacado |
|---|---:|---|
| `canonical_model` | 6 | company scope, Decimal, dirección, campos obligatorios |
| `completeness_model` | 6 | Unknown, auto-match, compuerta de cierre, aceptación |
| `connector_model` | 7 | egress, SSRF, credenciales bancarias, alcance E0 |
| `event_model` | 9 | propiedad del retry, DLQ sin raw, revalidación, autoridad, punto de control del lote |
| `golden_harness` | 7 | digest de input, traversal, autoridad de adjudicación |
| `idempotency_model` | 7 | composite UNIQUE, fingerprint, precheck, cross-company |
| `lineage_model` | 12 | engine release, tokens flotantes, SoD de overlay, gates, plan de transformación, excepción por fila |
| `privacy_model` | 7 | IA externa, autoridad de almacén, legal hold, clasificación |
| `quality_strategy` | 7 | dominios protegidos, cobertura promedio, gates |

Resultado del run completo tras FNC-P3.6 (`registry_digest` `8082aef…`):

```json
{"executed": 68, "outcomes": {"killed": 68},
 "unresolved": [], "source_tree_unchanged": true}
```

**Hoy no sobrevive ninguna**, y por eso `run` sale con cero. La sección siguiente
describe los dos supervivientes que hubo, y se conserva sin cambios: por qué
dejaron de serlo no se ha comprobado en esta ejecución, y darlo por arreglado
sería exactamente la clase de afirmación que este arnés existe para impedir.

### Los dos supervivientes que hubo

Se documentaron cuando el arnés los reportaba. Ambos caen en herramientas ya
integradas, fuera del alcance de FNC-QA-005.

| Mutación | Validador | Hallazgo | Owner | Gate |
|---|---|---|---|---|
| `MUT-PRV-006` | `privacy_model` | valida las rutas de evidencia por **existencia**, no por contención canónica: `docs/../docs/architecture/dfd-flows.json` se acepta | Security | S1-READY |
| `MUT-GHR-006` | `golden_harness` | `adjudication.runner_can_update_expected` se declara pero no se comprueba; solo `auto_update_expected_allowed` está aplicado | QA | S1-READY |

Mientras estuvieron vivos, `run` y `report` salían con exit distinto de cero, y
**ese era el resultado correcto**: había dos controles que el repositorio creía
tener y no tenía. Rebajar la severidad para forzar verde habría sido exactamente
el fallo que este arnés existe para detectar.

Observación relacionada y deliberadamente **no** codificada como mutación: `privacy_model`
también acepta una ruta de evidencia **absoluta** del host si ese fichero existe en la
máquina. No se declaró porque su resultado depende del host —moriría en CI y sobreviviría en
un portátil— y una mutación no determinista no pertenece a un registro adjudicado. Queda
como hallazgo para el owner de `privacy_model`.

---

## 8. Gaps declarados: cobertura que **no** se inventó

Cuatro riesgos no son atacables desde un contrato JSON. Se registran como gaps con owner y
gate bloqueado, en vez de fabricar una mutación que parezca cobertura:

| Riesgo | Por qué no es mutable aquí | Owner | Gate |
|---|---|---|---|
| `TM-002` | exige PostgreSQL real con RLS activo; en E0 no hay base de datos | Backend | DRG-01 |
| `TM-005` | cadena de suministro y firma de artefactos se verifican en CI e infraestructura | Security | DRG-00 |
| `TM-006` | el aislamiento de red y runtime del worker exige despliegue real | Platform | DRG-01 |
| `TM-010` | la superficie de IA está deshabilitada; solo se puede mutar la bandera | AI Platform | L-02 |

Las mutaciones de `data_ceiling` sobre seis contratos tocan la **declaración** asociada a
`TM-005`, no el perímetro. El gap sigue abierto.

---

## 9. Determinismo y replay

El `target_sha256` aplica la política explícita `utf8_lf_else_bytes`: normaliza
CRLF/CR a LF para texto UTF-8 y conserva los bytes exactos para binarios. El mismo
texto adjudicado mantiene así su identidad entre checkouts Windows y Linux.

El `deterministic_result_digest` de cada caso cubre registro, mutación, target y su digest,
expectativa, exit codes y códigos observados. **Excluye** duración, versión parche del
intérprete, hostname y timestamp: ninguno de ellos cambia el resultado, y meterlos haría que
dos ejecuciones idénticas produjeran digests distintos.

El manifiesto no contiene payloads, ni entorno, ni secretos: solo identificadores, digests y
veredictos.

---

## 10. CLI

```bash
python -m tools.mutation_harness.cli list
python -m tools.mutation_harness.cli verify
python -m tools.mutation_harness.cli run
python -m tools.mutation_harness.cli run --mutation MUT-CAN-002
python -m tools.mutation_harness.cli report
```

- `list` — mutaciones y gaps declarados, sin ejecutar nada.
- `verify` — valida el registro completo. Si falla, `run` **no ejecuta nada**.
- `run` — ejecuta y clasifica. Exit distinto de cero si hay superviviente bloqueante, caso
  sin resolver o si el árbol fuente cambió.
- `report` — resultados por riesgo y por control, con los gaps a la vista.
  `single_pass_score` es `null` **a propósito**: una nota agregada ocultaría justo los dos
  supervivientes.

---

## 11. El laboratorio sintético

`tests/golden/mutations/` contiene un contrato, una evidencia y un validador sintéticos, más
`MANIFEST.json` con el digest de cada uno. Nada describe un sistema, una entidad ni una
persona real, y hay prueba de que todo fichero está inventariado.

El validador sintético sabe portarse mal a propósito —aceptar todo, fallar por el motivo
equivocado, imprimir basura, pasarse del timeout, ensuciar la línea base— porque probar el
clasificador solo contra validadores que funcionan no demostraría que sabe distinguir un
control que muerde de un proceso que se cayó.

---

## 12. Límites honestos

1. Un run verde prueba que el arnés y sus expectativas son coherentes, **no** que el producto
   sea seguro.
2. Una mutación muerta prueba que **existe** una regla, no que la regla sea la correcta.
3. La cobertura se mide sobre contratos JSON, no sobre el sistema que algún día los cumplirá.
4. Los códigos esperados se derivaron observando los validadores reales y quedaron fijados: si
   un validador deja de emitirlos, la mutación sobrevive y el arnés lo dice. Eso detecta
   regresiones; no acredita que el código fuese correcto el primer día.
5. Ninguna nota agregada sustituye leer los supervivientes y los gaps.

## 13. Decisiones abiertas

| ID | Pregunta | Owner |
|---|---|---|
| `UD-QA-MUT-BUDGET` | Cadencia y presupuesto de ejecución del arnés en CI | QA |
| `UD-QA-MUT-SURVIVOR` | Quién adjudica un superviviente: arreglar el validador o aceptar el riesgo | QA |
| `UD-QA-MUT-EQUIVALENCE` | Criterio para declarar una mutación equivalente sin revisión caso a caso | Architecture |

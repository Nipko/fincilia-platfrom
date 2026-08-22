# Golden harness determinista y adjudicado

| Campo | Valor |
|---|---|
| Tarea | FNC-QA-003 |
| Estado | Review pending |
| Gate | S1-READY |
| Owners requeridos | QA |
| Revisores | Data, Accounting, Security |
| Registro ejecutable | `docs/testing/golden-harness.json` |
| Runner | `tools/golden_harness/` |
| Fixtures | `tests/golden/harness/` |
| Datos autorizados | Exclusivamente sintéticos |

Un harness deliberadamente pequeño. **No es un parser, ni un motor de matching, ni
producto.** Ejecuta suites adjudicadas contra versiones exactas, verifica resultados y
manifiestos, y falla ante drift, tampering, comandos no permitidos o datos no sintéticos.

---

## 1. CLI

```bash
python -m tools.golden_harness.cli list
python -m tools.golden_harness.cli verify
python -m tools.golden_harness.cli run
python -m tools.golden_harness.cli run --case GH-VALIDATE-LINEAGE
```

- `list` enumera los casos adjudicados sin ejecutar nada.
- `verify` valida el registro —hashes de entrada incluidos— sin ejecutar nada.
- `run` **verifica primero**: si el registro no valida, no se ejecuta ni un caso.

Salida JSON determinista y código de salida distinto de cero ante cualquier fallo,
incluida una selección de caso inexistente. Una selección vacía **nunca** es un éxito.

---

## 2. Casos adjudicados

Catorce, en tres suites:

| Suite | Casos |
|---|---|
| `contract_validators` | architecture, canonical, completeness, connector, cross-contract, DFD, events, idempotency, lineage, privacy, threat model y test strategy |
| `synthetic_corpus` | `GH-CORPUS-VERIFY` |
| `harness_selfcheck` | `GH-SELFCHECK` |

El self-check existe para que el harness ejercite de extremo a extremo la adjudicación de
inputs, el oráculo estructurado y la allowlist de módulos sin depender de ningún validador
ajeno: si todos los demás casos fallaran a la vez, ese seguiría distinguiendo un problema
del harness de un problema de los contratos.

**Docker y WSL quedan fuera.** FNC-PLT-001 y FNC-PLT-005 conservan sus jobs de integración.

---

## 3. Contrato de caso

`case_id`, suite, owner y revisores independientes, referencias de riesgo y de test,
runtime, `argv`, allowlist de módulos, `cwd`, timeout, límite de salida, inputs con ruta
relativa y SHA-256 adjudicado, clasificación de datos, exit code esperado, oráculo
estructurado, versiones que afectan al resultado, estado y gate consumidor.

**Veintiuna claves obligatorias.** Falta una y el caso no valida.

Para que la misma adjudicación funcione en Windows y Linux, los inputs textuales UTF-8
se canonicalizan a finales de línea LF antes del SHA-256. Los inputs binarios o el texto
no UTF-8 conservan bytes exactos. Esta política vive en `input_digest_policy`; cambiarla
es un cambio de contrato, no una decisión automática del runner.

---

## 4. Reglas de ejecución

| Regla | Cómo se aplica |
|---|---|
| Nunca shell | `subprocess.run` con lista `argv` y `shell=False`. Un `argv` que sea string se rechaza; un elemento con `&&`, `\|`, `;`, `>` o `$(` se rechaza |
| Solo módulos locales | `argv[0]` debe ser `-m`, el módulo debe estar en la allowlist del caso **y** bajo el espacio `tools.` |
| `cwd` contenido | se resuelve y se comprueba que queda dentro del repositorio |
| Rutas contenidas | sin absolutas, sin `..` —ni siquiera cuando resuelve dentro—, sin symlink que escape |
| Timeout obligatorio | entero positivo, máximo 300 s |
| Salida acotada | límite obligatorio, máximo 1 MiB; **una salida truncada nunca es PASS** |
| Cero red | por contrato, y el entorno del subproceso no hereda proxies |
| Entorno mínimo | allowlist de `PATH`, `SYSTEMROOT`, `COMSPEC`, `TEMP`, `TMP`, `LANG`, `LC_ALL`, más `PYTHONPATH`, `PYTHONHASHSEED=0`, `PYTHONIOENCODING`, `PYTHONDONTWRITEBYTECODE` y `PYTHONNOUSERSITE`. Ninguna credencial, ningún proxy |

---

## 5. Oráculos

`json_subset` · `json_equals` · `exit_code_only`.

Prohibidos por nombre: `always_pass`, `always_true`, `regex_loose`, `ignore_output`. Y
cualquier tipo fuera del allowlist se rechaza igualmente: el denylist explica **por qué**,
el allowlist cierra la puerta.

La normalización se limita a los campos que el caso declara explícitamente, y **jamás**
puede tocar `ok`, `errors`, `amount`, `currency`, `balance`, `total`, `digest`, `hash`,
`debit`, `credit` ni `count`. Normalizar una diferencia financiera es borrarla.

---

## 6. Manifiesto y digest determinista

Cada ejecución produce un manifiesto con: `case_id`, suite, resultado, motivos, timeout,
truncamiento, runtime, `registry_digest`, `case_digest`, digests de entrada, exit code
esperado y observado, digest de la salida normalizada y `deterministic_result_digest`.

El digest determinista se calcula sobre seis campos: registro, caso, entradas, exit code
esperado, exit code observado y salida normalizada.

**Quedan fuera a propósito:** duración, versión concreta del intérprete, hostname y
timestamp. Ninguno cambia el resultado adjudicado; la salida sí. Por eso un replay idéntico
conserva el digest, y cualquier cambio de contrato, caso o salida produce una clave nueva.

El manifiesto **no transporta** stdout, stderr, entorno ni secretos. Solo digests, códigos
y motivos acotados.

---

## 7. Adjudicación

El runner **no adjudica**. No actualiza expected outputs, no actualiza digests de entrada
y no toca los fixtures. `auto_update_expected_allowed` es `false` y hay una prueba que
comprueba que registro, fixture y manifiesto conservan su hash después de un `run`.

Cuando un contrato cambia legítimamente, `verify` **falla**, y esa es la intención: el
digest registrado dejó de corresponder. El procedimiento es humano:

1. revisar el diff del contrato y decidir si el cambio es correcto;
2. actualizar en el registro los digests de entrada y, si procede, la expectativa;
3. obtener revisión independiente — quien cambió el contrato no adjudica su propio caso;
4. volver a ejecutar `verify` y `run`.

No existe ni existirá un comando que haga los pasos 1 a 3 por su cuenta.

---

## 8. Fixtures

Bajo `tests/golden/harness/`, con `MANIFEST.json` que inventaría cada fichero con su
SHA-256 y declara procedencia y clasificación. Creados desde cero; no derivan de ningún
documento real. Los dominios usados son reservados (`example.invalid`).

**Los cinco fixtures de FNC-DAT-002 bajo `tests/golden/synthetic/` no se modifican.**

---

## 9. Verificación

```bash
python -m tools.golden_harness.cli verify
python -m tools.golden_harness.cli run
python -m unittest tools.golden_harness.test_harness -v
```

## 10. Límites conocidos

1. **El harness prueba contratos, no producto.** Que los catorce casos pasen significa que los modelos ejecutables son mutuamente coherentes, no que exista código que los implemente.
2. **Un cambio de contrato rompe CI hasta re-adjudicar.** Es deliberado y tiene coste operativo: conviene que el Steward lo tenga presente al planificar cambios de contrato.
3. **No cubre integración real.** RLS, pool, outbox y restore siguen en los jobs de PLT-001 y PLT-005.
4. **El intérprete queda fuera del digest.** Dos versiones de Python que produzcan salidas idénticas dan el mismo digest; si alguna vez produjeran salidas distintas, el digest lo detectaría por la vía de la salida, no por la del intérprete.

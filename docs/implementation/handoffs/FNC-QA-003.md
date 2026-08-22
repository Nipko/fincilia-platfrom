---
task: FNC-QA-003
status: REVIEW_PENDING
base_sha: c227f1c
base_sha_verified: false
integration_sha: see_git_commit_containing_this_handoff
implementer: Claude (external principal dev)
data_used: synthetic_only
human_acceptance: pending
quality_gate_on_git_index: pass_during_integration
---

# Handoff FNC-QA-003 — Golden harness determinista y adjudicado

- **Estado:** `REVIEW_PENDING`
- **Agente:** Claude (external principal dev)
- **Accountable owner:** UNASSIGNED
- **Revisores requeridos:** QA, Data, Accounting, Security
- **Base declarada:** `c227f1c`, entregada por el Integration Steward
- **Head SHA:** no disponible — el encargo prohíbe usar Git; no verifiqué la base ni puedo aportar head
- **Rama/worktree:** no aplica; escritura directa sobre el árbol compartido

No declaro gates, ADR, releases, riesgos ni decisiones humanas como aceptados. Sin datos
reales, red, credenciales ni conectores.

## 1. Objetivo y resultado

Un harness local y de CI que ejecuta suites adjudicadas contra versiones exactas, verifica
resultados y manifiestos, produce evidencia determinista y falla ante drift, tampering,
comandos no permitidos o datos no sintéticos.

Deliberadamente pequeño: **no construí parser, matching ni producto**. Adjudica los once
validadores offline existentes, el validador de estrategia de FNC-QA-002, la verificación
del corpus sintético y un self-check propio.

## 2. Paths modificados

| Ruta | Estado | Bytes |
|---|---|---:|
| `docs/testing/GOLDEN_HARNESS.md` | nuevo | 6.956 |
| `docs/testing/golden-harness.json` | nuevo, registro adjudicado | 24.822 |
| `tools/golden_harness/__init__.py` | nuevo | 71 |
| `tools/golden_harness/registry.py` | nuevo, carga y validación estricta | 12.442 |
| `tools/golden_harness/runner.py` | nuevo, ejecución aislada y manifiesto | 8.014 |
| `tools/golden_harness/cli.py` | nuevo, `list` / `verify` / `run` | 4.039 |
| `tools/golden_harness/selfcheck.py` | nuevo, caso de auto-verificación | 1.538 |
| `tools/golden_harness/test_harness.py` | nuevo | 20.402 |
| `tests/golden/harness/MANIFEST.json` | nuevo, inventario con SHA-256 | 413 |
| `tests/golden/harness/README.md` | nuevo, procedencia | 793 |
| `tests/golden/harness/sample_case_input.json` | nuevo, fixture sintético | 489 |
| `docs/implementation/handoffs/FNC-QA-003.md` | nuevo, este documento | — |

**Paths reservados que se liberan:** los cinco de la ficha.

**Los cinco fixtures de FNC-DAT-002 bajo `tests/golden/synthetic/` no fueron modificados**,
verificado por timestamp e integridad: `synthetic_corpus verify` sigue en verde.

## 3. Conteos

| Bloque | Cantidad |
|---|---:|
| Casos adjudicados | **14** en 3 suites |
| Claves obligatorias por caso | 21 |
| Inputs adjudicados con SHA-256 | 41 entradas en total |
| Runtimes permitidos | 1 (`python`, vía `sys.executable`) |
| Tipos de oráculo permitidos | 3; 4 denylisted por nombre |
| Variables de entorno heredables | 7, más 5 fijadas por el runner |
| Códigos de error del registro | 34 únicos |
| Pruebas | **34** |

Casos: doce de `contract_validators` (architecture, canonical, completeness, connector,
cross-contract, DFD, events, idempotency, lineage, privacy, threat model, test strategy),
uno de `synthetic_corpus` y uno de `harness_selfcheck`.

## 4. Comandos ejecutados y resultado exacto

```powershell
python -m tools.golden_harness.cli list
python -m tools.golden_harness.cli verify
python -m tools.golden_harness.cli run
python -m tools.golden_harness.cli run --case GH-VALIDATE-LINEAGE
python -m unittest tools.golden_harness.test_harness -v
```

| Comando | Resultado observado |
|---|---|
| `cli list` | 14 casos, todos `active`, exit 0 |
| `cli verify` | `{"ok": true, "errors": [], "cases": 14}`, exit 0 |
| `cli run` | **14 ejecutados, 14 PASS, 0 fallidos**, exit 0 |
| `cli run --case …` | 1 ejecutado, exit 0 |
| `unittest tools.golden_harness.test_harness` | `Ran 34 tests` · `OK` |

Los dieciocho escenarios negativos del encargo están materializados como `test_neg_01` …
`test_neg_18`, más `test_neg_05b`, `test_neg_08b` y siete refuerzos.

### 4.1 Mutación del runner y del registro

Ocho mutaciones sobre reglas críticas, en copia fuera del repositorio:

| Mutante | Regla eliminada | Resultado |
|---|---|---|
| M1 | verificación del hash de input | **muere** |
| M2 | rechazo de `argv` como string | **muere** |
| M3 | allowlist de módulos | **muere** |
| M4 | rechazo de `..` en rutas | **sobrevivió**, luego corregido |
| M5 | denylist de oráculos | **sobrevivió**, luego corregido |
| M6 | rechazo de caso no `active` | **muere** |
| M7 | entorno mínimo, sin proxies | **muere** |
| M8 | selección vacía como éxito | **muere** |

Dos supervivientes y qué revelaron:

- **M4.** El rechazo sintáctico de `..` era redundante con la comprobación de contención por `relative_to`, porque mis rutas de prueba resolvían fuera del repositorio. Añadí el caso que las distingue: `docs/../docs/architecture/dfd-flows.json` **resuelve dentro** y aun así debe rechazarse, porque dos grafías del mismo fichero harían ambigua la contabilidad de digests. Con esa prueba, M4 muere.
- **M5.** El denylist por nombre (`always_pass`, `always_true`, `regex_loose`, `ignore_output`) era redundante con el allowlist. Los separé en dos códigos —`GH-ORACLE-FORBIDDEN` explica *por qué*, `GH-ORACLE-KIND` cierra la puerta— y la prueba exige ambos. Con eso, M5 muere.

Añadí además `test_neg_08b`, que surgió al examinar un noveno mutante casi equivalente: con
un oráculo `exit_code_only`, un truncamiento de salida sería invisible salvo que el runner
lo trate como fallo por sí mismo. Ahora lo hace y hay prueba que lo fija.

## 5. Decisiones tomadas dentro del alcance

1. **`run` verifica primero.** Si el registro no valida, no se ejecuta ni un caso y el exit code es 1.
2. **El digest determinista excluye duración e intérprete concreto**, e incluye registro, caso, entradas, exit code esperado y observado, y salida normalizada. Ninguno de los excluidos cambia el resultado adjudicado; la salida sí.
3. **Una salida truncada nunca es PASS**, aunque el oráculo no lea stdout.
4. **Una selección de caso inexistente devuelve exit 1**, no un éxito vacío.
5. **El runner no adjudica.** No actualiza expected outputs ni digests, y hay prueba de que registro, fixture y manifiesto conservan su hash tras un `run`.
6. **El manifiesto no transporta stdout, stderr, entorno ni secretos.** Hay prueba que lo verifica sobre el manifiesto serializado.
7. **El self-check existe para separar fallos del harness de fallos de los contratos.** Si todos los validadores fallaran a la vez, ese caso distingue una causa de la otra.

## 6. Hallazgos fuera de scope

1. **`docs/testing/TEST_CATALOG.md` divergía de los contratos** en el momento de mi medición. Está detallado en el handoff de FNC-QA-002 §6 y registrado como `UD-QA-CATALOG-DRIFT`. No edité el catálogo.
2. **`tools/` no es un paquete importable**, así que `python -m unittest discover -s tools -p "test_*.py"` falla con `ImportError: Start directory is not importable`. No es un defecto que yo introdujera y no está entre los comandos del encargo, pero conviene saberlo: la suite integrada se ejecuta por módulo o con `-t .` sobre cada subpaquete. **Owner sugerido: Integration Steward.**
3. **Un cambio legítimo de contrato romperá `verify` hasta re-adjudicar.** Es la intención del diseño, pero tiene coste operativo real y conviene tenerlo presente al planificar cambios de contrato. El procedimiento humano está en `GOLDEN_HARNESS.md` §7.

## 7. Riesgos

1. **El harness prueba contratos, no producto.** Catorce casos en verde significan que los modelos ejecutables son mutuamente coherentes, no que exista código que los implemente.
2. **La adjudicación es manual por diseño.** Sin auto-update, cada cambio de contrato exige actualizar digests y obtener revisión independiente. Si esa disciplina se relaja, alguien acabará copiando digests sin mirar el diff, y el harness pasará a certificar el drift en vez de detectarlo.
3. **No cubre integración real.** RLS, pool, outbox, worker sandbox y restore siguen en los jobs de PLT-001 y PLT-005; este harness no los sustituye.
4. **El aislamiento del subproceso es de entorno, no de kernel.** El runner controla `argv`, `cwd`, entorno, timeout y salida, pero no impide por sí mismo una llamada de red si un módulo local la intentara: la garantía de cero red es contractual y está respaldada por los propios validadores, que no importan `socket` ni `urllib`.
5. **`sys.executable` es el intérprete del proceso padre.** Local 3.11, CI 3.12. El registro declara `python_minimum_minor: "3.11"` y el digest excluye la versión concreta; si dos versiones produjeran salidas distintas, el digest lo detectaría por la salida.

## 8. Compatibilidad y consumidores

Añade un módulo (`tools/golden_harness`), un registro (`docs/testing/golden-harness.json`)
y tres fixtures nuevos bajo `tests/golden/harness/`. No cambia esquemas, eventos, contratos
ni herramientas existentes. Los once validadores hermanos, `quality_strategy` y
`synthetic_corpus verify` siguen en verde tras el cambio.

## 9. Rollback

Eliminar `docs/testing/GOLDEN_HARNESS.md`, `docs/testing/golden-harness.json`,
`tools/golden_harness/`, `tests/golden/harness/` y este handoff. Nada más que revertir:
ningún fixture ni contrato existente fue modificado.

## 10. Instrucciones para el Integration Steward

1. Indexar las once rutas de §2 más este handoff.
2. Ejecutar `python -m tools.quality_gate.cli` sobre el índice. **No lo ejecuté ni lo declaro exitoso.**
3. Añadir a CI, en `lane_golden`: `python -m tools.golden_harness.cli verify`, `python -m tools.golden_harness.cli run` y `python -m unittest tools.golden_harness.test_harness`.
4. **Verificar el orden en CI:** el harness debe correr *después* de los validadores de contrato, porque su `verify` depende de los digests de esos contratos.
5. Completar `integration_sha` aquí y en `docs/implementation/tasks/FNC-QA-003.md`, que no modifico.
6. Actualizar `CURRENT_PHASE.md`, backlog y trazabilidad: `FNC-QA-003` a *Review pending*.
7. Añadir al `TEST_CATALOG.md` los catorce `GH-*` como casos adjudicados, si procede según su criterio de nomenclatura.
8. **Decidir sobre el hallazgo 2 de §6**: si `tools/` debe volverse importable para que `discover -s tools` funcione en CI.
9. **No marcar** ningún gate como superado. El registro y el validador lo rechazarán.

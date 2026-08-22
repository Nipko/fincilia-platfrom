# Handoff — FNC-PLT-007: CLI segura de desarrollo y diagnóstico local

| Campo | Valor |
|---|---|
| Tarea | FNC-PLT-007 |
| Estado | **`REVIEW_PENDING`** |
| Base declarada | `48b21d1` — entregada por el Integration Steward, **no verificada** |
| Verificación de la base | No se usó Git en ninguna forma |
| `integration_sha` | `pending_integration_steward` |
| `quality_gate_on_git_index` | `pending_integration_steward` |
| Owner | Platform |
| Revisores independientes | Security, Developer Experience, QA |
| Gate | S1-READY — `not_met` |

---

## 1. Rutas creadas

| Ruta | Acción |
|---|---|
| `docs/platform/developer-cli.json` | creada — contrato autoritativo |
| `docs/platform/DEVELOPER_CLI.md` | creada — documentación |
| `tools/dev_cli/__init__.py` | creada |
| `tools/dev_cli/registry.py` | creada — allowlist cerrado y validación del contrato |
| `tools/dev_cli/process.py` | creada — capa de proceso y lock de stack |
| `tools/dev_cli/cli.py` | creada — `doctor`/`validate`/`test`/`stack`/`evidence` |
| `tools/dev_cli/test_cli.py` | creada — 78 pruebas |
| `docs/implementation/handoffs/FNC-PLT-007.md` | este documento |

**No se tocó** `infra/local/compose.yaml`, CI, `CURRENT_PHASE.md`, backlog,
trazabilidad, work graph, gates, decisiones, ownership, tareas, ADR ni contrato
alguno. Todas las rutas reservadas quedan liberadas.

---

## 2. Contrato y decisiones implementadas

- **Allowlist cerrado de módulos en el código.** El contrato *elige* de él; no lo
  amplía. Un registro capaz de introducir un módulo nuevo sería un ejecutor de
  comandos disfrazado de configuración.
- **Solo `-m <módulo>`**, lista `argv`, `shell=False`, sin metacaracteres, `cwd`
  confinado.
- **Entorno filtrado dos veces**: por allowlist del contrato y otra vez en código
  contra `PROXY`, `TOKEN`, `SECRET`, `KEY`, `PASSWORD` y `CREDENTIAL`.
- **Timeout, truncamiento, dependencia ausente y argv rechazado nunca son PASS.**
- **`stack down` sin `--volumes` ni `--remove-orphans`**, sobre `fincilia-local` y su
  propio Compose, ambos fijados en el contrato.
- **Lock `O_EXCL`** para los dos comandos mutadores; el error nombra el fichero exacto.
- **Degradación**: `doctor`, `validate`, `test` y `evidence` funcionan sin Docker.
- **Cinco códigos de salida** declarados y exigidos como conjunto exacto.
- **`aggregate_score: null`**: un promedio ocultaría el check que falló.

Las 16 invariantes negativas del encargo tienen prueba negativa.

---

## 3. Comandos exactos y resultado

| Comando | Exit | Resultado |
|---|---:|---|
| `python -m unittest tools.dev_cli.test_cli` | 0 | **78 pruebas, OK** |
| `python -m tools.dev_cli.cli doctor` | 0 | Python 3.11.6 ✓, contrato válido, 3 dependencias Docker ausentes (opcionales), 0 rutas ausentes |
| `python -m tools.dev_cli.cli validate --group all` | **1** | 25 ejecutados, 24 pass, 1 fail, **0 fallos inesperados** |
| `python -m tools.dev_cli.cli evidence summary` | 0 | 12 fuentes, 32 decisiones abiertas, 0 con aceptación humana |
| `python -m tools.dev_cli.cli stack status` | **3** | `dependency_missing` con diagnóstico estable |

`stack down` **no se ejecutó** contra ningún entorno: no se levantó ninguno con esta
CLI. Sus semánticas se prueban con dobles sobre el argv construido, y esos tests
**no** son evidencia de integración Docker.

El único fallo de `validate --group all` es `security-supply-chain`, que falla porque
SBOM, firma y procedencia no están demostradas. Es un gap declarado de FNC-SUP-001
que bloquea DRG-00, no una regresión.

---

## 4. Pruebas negativas y qué demostraron

| Invariante | Degradación | Regla |
|---|---|---|
| 1 | módulo `os`, proyecto `fincilia-db-spike`, Compose de otro spike, `cwd: ../elsewhere` | `DVC-MODULE-ALLOWLIST`, `DVC-COMPOSE-PROJECT`, `DVC-COMPOSE-FILE`, `DVC-CWD` |
| 2 | argv como string; `&&`, `;`, `\|`, backticks, `$( )`, `*`, `~` | `DVC-ARGV-LIST`, `DVC-ARGV-SHELL` |
| 3 | escaneo del código fuente | sin `shell=True`, `eval`, `exec`, `os.system`, `popen` |
| 4 | ruta absoluta, `..` interno, symlink | `safe_relative` / `resolve_inside` |
| 5 | `HTTP_PROXY`, `GITHUB_TOKEN`, `AWS_SECRET_ACCESS_KEY`, `API_KEY` en el allowlist | `DVC-ENV-LEAK` y filtro en código |
| 6 | salida de 20 000 bytes con tope de 100 | `failed`, `truncated: true` |
| 7 | proceso que duerme 5 s con timeout de 1 | `timeout`, nunca `passed` |
| 8 | `validate --group security` con un check en rojo | el check sobrevive en `failed_checks` |
| 9 | `removes_volumes`, `removes_orphans`, `purges_data`, `seeds_real_data`, `runs_product_migrations` | `DVC-STACK-DESTRUCTIVE`; y el argv de `down` no contiene ninguna de esas banderas |
| 10 | dos `StackLock` sobre el mismo directorio | el segundo es rechazado nombrando el fichero |
| 11 | `doctor_requires_docker: true` | `DVC-DEGRADATION` |
| 12 | búsqueda de `PASSWORD`, `SECRET`, `token`, `@gmail`, `NIT` en la salida | ninguno aparece |
| 13 | `writes_gate_or_status: true`, gate `met`, aceptación humana | `DVC-AUTHORITY`, `DVC-GATE`, `DVC-ACCEPTANCE` |
| 14 | tres ejecuciones consecutivas | `developer-cli.json` intacto byte a byte |
| 15 | registro invertido | misma selección, mismo orden, mismos conteos |
| 16 | binario inexistente | `dependency_missing` con diagnóstico, sin traceback |

---

## 5. Hallazgo propio corregido: tres `expected_today` obsoletos

Se escribieron cuatro notas `expected_today` y **tres resultaron falsas** contra la
base `48b21d1`, porque el Integration Steward ya había corregido lo que describían:

| Nota retirada | Por qué era falsa en esta base |
|---|---|
| `qa-catalog` | el catálogo ya está reconciliado; `test_catalog validate` sale 0 con 65 hallazgos no bloqueantes |
| `test-unit-governance` | `FNC-PLT-006` ya figura en el backlog; `tools.work_graph` pasa |
| `test-mutation-run` | los dos supervivientes ya están corregidos; 63/63 muertas y `known_survivors` vacío |

Queda **una sola**, la de supply chain, que sí corresponde. Una nota que nadie revisa
se convierte en ruido aceptado, y por eso la decisión `UD-PLT-CLI-EXPECTED` queda
abierta con owner QA.

---

## 6. Hallazgos fuera de scope

| Ruta | Regla | Impacto | Owner |
|---|---|---|---|
| entorno de la máquina | disponibilidad de Docker | En este Windows, Docker vive dentro de WSL y no responde al binario directo. La CLI lo diagnostica y sigue funcionando, pero `stack` queda inutilizable sin ejecutarla desde WSL. Atravesar el límite automáticamente sería construir un comando que nadie declaró. | Platform |

No se corrigió: la decisión es de Platform (`UD-PLT-CLI-WSL`).

---

## 7. Riesgos que permanecen

- **La CLI puede volverse una autoridad de facto** si CI empieza a invocarla y nadie
  mantiene la equivalencia con los comandos enumerados (`UD-PLT-CLI-CI`).
- **`validate --group all` sale 1 mientras exista un gap declarado.** Es correcto, pero
  un rojo permanente es fácil de ignorar; de ahí la separación entre
  `unexpected_failures` y `expected_failures`.
- **El lock es local al sistema de ficheros**: no coordina entre máquinas ni sobrevive
  a un proceso que muera sin liberar. El mensaje de error nombra el fichero a borrar.

---

## 8. Rollback

Eliminar `tools/dev_cli/`, `docs/platform/developer-cli.json` y
`docs/platform/DEVELOPER_CLI.md`. No modifica nada ajeno, así que el rollback es
total. Dependencia entrante: ninguna; FNC-GAT-003 no invoca esta CLI, lee
`developer-cli.json` como fuente de gates y decisiones.

---

## 9. Compatibilidad

Solo lee y ejecuta contratos existentes. No cambia el comportamiento de ninguno. Si
un validador ajeno cambia su exit code, esta CLI lo reflejará sin traducirlo.

---

## 10. Pasos para el Integration Steward

1. **Indexar** las rutas de §1.
2. **Ejecutar el quality gate sobre el índice Git.** No se ejecutó aquí.
3. **CI**: decidir si CI invoca esta CLI o mantiene su lista enumerada. Hoy CI enumera;
   duplicar la lista en dos sitios es la deuda que `UD-PLT-CLI-CI` plantea.
4. **Catálogo y trazabilidad**: `developer-cli.json` no declara `required_tests`, así
   que no introduce IDs ni drift.
5. **Digests golden/mutation**: ninguno deriva. `developer-cli.json` no es input de
   ningún caso golden ni de ninguna mutación registrada.
6. **Revisar el único `expected_today`** que queda y fijar su cadencia de revisión.
7. **Decidir `UD-PLT-CLI-WSL`** con Platform.
8. **Liberar reservas** de FNC-PLT-007.

Estado final: **`REVIEW_PENDING`**. No se declara aceptación, integración, head SHA,
CI remoto ni revisión humana inexistentes. Esta CLI no marca ningún gate.

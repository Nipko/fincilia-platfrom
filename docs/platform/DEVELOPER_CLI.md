# CLI segura de desarrollo y diagnóstico local

| Campo | Valor |
|---|---|
| Tarea | FNC-PLT-007 |
| Estado | Review pending |
| Gate | S1-READY — `not_met` |
| Owner | Platform |
| Revisores independientes | Security, Developer Experience, QA |
| Contrato autoritativo | `docs/platform/developer-cli.json` |
| CLI | `python -m tools.dev_cli.cli` |
| Datos | Exclusivamente sintéticos, puertos locales |

---

## 1. Qué es

Un compositor. Ejecuta contratos que **ya existen**, con argv fijo y resultados
observables. Lo que no es, importa más:

- no es una segunda fuente de verdad sobre gates, estados ni secretos;
- no instala, no actualiza, no purga, no resetea, no siembra datos;
- no ejecuta migraciones de producto;
- no toca cloud, secretos ni configuración;
- no decide el estado de ningún gate.

Reducir comandos manuales es útil. Crear una autoridad paralela sería caro y
silencioso, así que el contrato lo prohíbe de forma ejecutable y hay prueba de ello.

---

## 2. Comandos

```bash
python -m tools.dev_cli.cli doctor
python -m tools.dev_cli.cli validate [--group core|security|data|qa|all]
python -m tools.dev_cli.cli test [--group unit|golden|mutation|all]
python -m tools.dev_cli.cli stack status|up|down
python -m tools.dev_cli.cli evidence summary
```

`--format json|text`. JSON es la representación canónica; el texto es una vista y
nunca contiene nada que el JSON no contenga.

| Comando | Clasificación |
|---|---|
| `doctor`, `validate`, `test`, `evidence summary`, `stack status` | `read_only` |
| `stack up`, `stack down` | `local_reversible` |

---

## 3. Cómo se ejecuta un check

- lista `argv`, `shell=False`, sin excepciones;
- solo `-m <módulo>`, y el módulo tiene que estar en un **allowlist cerrado que vive
  en el código**. El contrato *elige* de ese allowlist; no lo amplía. Un registro que
  pudiera introducir un módulo nuevo sería un ejecutor de comandos disfrazado de
  configuración;
- `cwd` confinado al árbol, rechazando absolutas, `..` y symlinks;
- entorno por allowlist, filtrado **otra vez** en código contra `PROXY`, `TOKEN`,
  `SECRET`, `KEY`, `PASSWORD` y `CREDENTIAL`, de modo que ampliar el allowlist por
  descuido en el contrato no basta para filtrar nada;
- timeout y tope de salida por check.

### Qué no cuenta como PASS

| Situación | Resultado |
|---|---|
| exit distinto de cero | `failed` |
| timeout | `timeout` |
| salida truncada | `failed` — si no se pudo leer el resultado, no se sabe |
| dependencia ausente | `dependency_missing` |
| argv rechazado | `refused` |

Ninguno se redondea a aprobado. `validate all` conserva el resultado individual de
cada check y `aggregate_score` es `null` a propósito.

---

## 4. `expected_today`: explicar sin absolver

Un check puede llevar una nota `expected_today` que explique por qué su fallo ya se
conocía. Esa nota **no cambia el exit code** y el check sigue contando como fallo;
solo separa `unexpected_failures` de lo ya sabido, para que un fallo nuevo no se
pierda entre el ruido.

Hoy queda **una sola**: `security-supply-chain`, que falla porque SBOM, firma y
procedencia no están demostradas —un gap declarado que bloquea DRG-00—.

Durante la construcción se escribieron cuatro y tres resultaron **obsoletas** contra
la base `48b21d1`: el catálogo de pruebas ya estaba reconciliado, el work graph ya
no reportaba la tarea huérfana y los dos supervivientes de mutación ya estaban
corregidos. Se retiraron. Una nota que nadie revisa se convierte en ruido aceptado,
que es justo lo que la decisión abierta `UD-PLT-CLI-EXPECTED` plantea.

---

## 5. Degradación

`doctor`, `validate`, `test` y `evidence summary` funcionan **sin Docker**. Solo
`stack` lo necesita, y cuando falta devuelve un diagnóstico estable con exit
`dependency_missing`, nunca un traceback:

```json
{"command": "stack up", "ok": false,
 "reason": "Docker is not available. `doctor`, `validate` and `test` keep working without it."}
```

En un Windows con Docker dentro de WSL, la CLI **no** atraviesa el límite por su
cuenta: construir un comando que nadie declaró sería exactamente lo que el allowlist
existe para impedir. El diagnóstico dice que se ejecute desde WSL, y la decisión
`UD-PLT-CLI-WSL` queda abierta.

---

## 6. El stack local

- Único proyecto tocable: **`fincilia-local`**, con `infra/local/compose.yaml`. Ambos
  fijados en el contrato y comprobados antes de construir el argv.
- `stack down` es deliberadamente `docker compose down` **a secas**. `--volumes`
  borraría el volumen local con nombre, y `--remove-orphans` puede tocar contenedores
  que otro proyecto dejó colgando. Si alguien esperaba que dejara la base limpia, no
  lo hace, y es a propósito.
- `stack up` y `stack down` toman un **lock local** creado con `O_EXCL`, de modo que
  la exclusión la garantiza el sistema de ficheros y no una comprobación previa que
  podría perder la carrera. Si otro run lo tiene, el error nombra el fichero exacto
  a borrar.

---

## 7. Registro actual

25 checks de validación en cuatro grupos y 10 de prueba en tres:

| Grupo | Checks | Cubre |
|---|---:|---|
| `core` | 8 | arquitectura, canónico, cross-contract, ADR, work graph, workspace, runtime config, stack local |
| `security` | 4 | threat model, privacidad, región, cadena de suministro |
| `data` | 8 | completitud, idempotencia, linaje, DFD, eventos, conectores, migraciones |
| `qa` | 5 | estrategia, catálogo, golden, mutación, corpus sintético |
| `unit` | 6 | suites unitarias por dominio |
| `golden` | 2 | arnés golden y sus casos |
| `mutation` | 2 | arnés de mutaciones y su ejecución |

Resultado medido de `validate --group all`: **25 ejecutados, 24 pasan, 1 falla**
(`security-supply-chain`), 0 fallos inesperados. Exit 1, que es el resultado honesto.

---

## 8. `evidence summary`

Lee 12 contratos estructurados y resume estado, aceptación humana, techo de datos,
gates no cumplidos y decisiones abiertas. **No ejecuta nada y no produce evidencia
nueva.** Medición actual: 12 fuentes, **32 decisiones sin resolver, ninguna fuente
con aceptación humana registrada**.

---

## 9. Códigos de salida

| Nombre | Código |
|---|---:|
| `ok` | 0 |
| `check_failed` | 1 |
| `invalid_usage` | 2 |
| `dependency_missing` | 3 |
| `timeout` | 4 |

El contrato los declara y el validador exige que sean exactamente esos: cambiarlos
en silencio rompería a cualquiera que los interpretara.

---

## 10. Límites honestos

1. Un `doctor` en verde dice que las herramientas responden, **no** que el repositorio esté correcto.
2. Esta CLI no es autoridad sobre ningún gate, estado ni decisión.
3. No instala, no actualiza, no purga, no resetea, no siembra y no migra nada de producto.
4. `stack down` no borra volúmenes.
5. Un `expected_today` explica un fallo conocido; no lo convierte en aprobado.
6. No lee ni imprime `.env`, entorno completo ni rutas de usuario innecesarias.

## 11. Decisiones abiertas

| ID | Pregunta | Owner |
|---|---|---|
| `UD-PLT-CLI-WSL` | Si la CLI debe atravesar WSL o si se documenta ejecutarla desde WSL | Platform |
| `UD-PLT-CLI-CI` | Si CI debe invocar esta CLI en vez de enumerar comandos, y quién mantiene la equivalencia | Platform |
| `UD-PLT-CLI-EXPECTED` | Cadencia de revisión de los `expected_today` | QA |

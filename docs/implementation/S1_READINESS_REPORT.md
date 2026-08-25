# Readiness S1 ejecutable y fail-closed

| Campo | Valor |
|---|---|
| Tarea | FNC-GAT-003 |
| Estado | Review pending |
| Gate objetivo | **S1-READY — `not_met`**, aceptación `pending_human` |
| Owner | Integration Steward |
| Revisores independientes | Product, Architecture, Security, Accounting, QA |
| Contrato autoritativo | `docs/implementation/s1-readiness.json` |
| CLI | `python -m tools.s1_readiness.cli` |

---

## 1. El problema

El repositorio tiene muchos contratos válidos y muchas decisiones humanas
pendientes. Un validador en verde acredita **un contrato ejecutable**; no acredita
una aprobación. Sin algo que mantenga esas dos dimensiones separadas, la acumulación
de verdes acaba leyéndose como progreso hacia un gate que nadie ha firmado.

Este agregador existe para que un agente no pueda convertir «ejecutable» en
«aprobado», ni siquiera sin querer.

---

## 2. Regla de composición

**Conjuntiva y fail-closed.** S1-READY solo puede estar `met` si *todos* sus
requisitos están satisfechos, y la única categoría que satisface es `machine_pass`.

| Categoría | ¿Satisface? |
|---|---|
| `machine_pass` | **sí** |
| `machine_fail` | no |
| `not_executed` | no — un check sin ejecutar nunca es un pase |
| `pending_human` | no — la ausencia de una decisión no es una aprobación |
| `blocked_dependency` | no |
| `stale_evidence` | no |
| `contradiction` | no |

---

## 3. De dónde sale el estado

Solo de **fuentes estructuradas**. El repositorio declara que, si el documento y el
modelo difieren, manda el modelo; el agregador no invierte esa jerarquía y el
validador rechaza cualquier fuente en Markdown narrativo.

- **21 modelos JSON** con sus claves de gates y de decisiones declaradas explícitamente.
- **Front-matter** de las fichas de tarea y de `CURRENT_PHASE.md`.
- La prosa se cita; nunca se convierte en estado.

Sobre el front-matter: se lee un subconjunto estricto —`clave: valor`,
`clave: [a, b]` y listas de bloque `clave:` + `  - elemento`—. Cualquier otra
construcción se declara ilegible en vez de adivinarse, y una fuente ilegible
invalida la evaluación entera.

### Conjuntos dinámicos, no listas paralelas

Dos requisitos se resuelven **descubriendo**, no citando:

- `adr_set` lee `required_s1_adrs` de `adr-readiness.json`. Si alguien añade un ADR
  requerido, aparece solo.
- `decision_set` recoge toda decisión cuya fuente declare expresamente
  `blocks: [S1-READY]`. Una decisión nueva que bloquee S1 no puede quedar fuera;
  las decisiones de DRG, A-02, L-01/02, S-01 o GA siguen visibles sin falsear este gate.

Una lista copiada a mano habría envejecido en la primera integración.

---

## 4. Contradicciones: se reportan, no se resuelven

Cuando dos fuentes estructuradas dicen cosas distintas del mismo sujeto, elegir una
en silencio sería inventar autoridad. El agregador reporta todas las contradicciones,
pero solo bloquea S1 si afectan S1-READY, sus owners, un ADR requerido o una decisión
que declare bloquear S1.

**Dos contradicciones reales observadas hoy:**

| Sujeto | Campo | Valores | Fuentes |
|---|---|---|---|
| `DRG-00` | `owner_role` | `Legal` / `Security` | `privacy-map.json$.gates[1]` · `lineage-model.json$.gates[1]` |
| `DRG-01` | `owner_role` | `Legal` / `Security` | `privacy-map.json$.gates[2]` · `lineage-model.json$.gates[2]` |

La adjudicación sigue siendo humana. Estas dos contradicciones pertenecen a gates de
datos reales posteriores y por eso no alteran el veredicto de S1 sintético.

---

## 4bis. Triaje de contradicciones (FNC-GAT-004)

La relevancia se **declara** en `contradiction_relevance`; no se deduce de qué requisitos
existan. Deducirla la volvía invisible: bastaba retirar un requisito de tipo `gate` para
que una contradicción dejara de bloquear sin que nadie lo hubiera decidido.

Una contradicción cae en exactamente una de tres cajas:

| Caja | Significa | Efecto |
|---|---|---|
| `blocking` | recae sobre el gate objetivo, un owner slot exigido, un ADR requerido o una decisión que declara bloquear S1 | bloquea S1-READY |
| `acknowledged` | enrutada con `owner_role`, `gate`, `reason` y `blocks_gate: true` | no bloquea S1-READY; **sigue bloqueando su propio gate** |
| `unrouted` | nadie la enrutó | **bloquea S1-READY** — el silencio no es una resolución |

Enrutar no resuelve: el validador rechaza `blocks_gate: false` y rechaza que una ruta
apunte al propio gate objetivo.

Estado actual: `blocking 0 · acknowledged 2 · unrouted 0`. Las dos contradicciones de
`DRG-00` y `DRG-01` están enrutadas a **Integration Steward**, con revisores Legal y
Security, y siguen bloqueando sus gates.

---

## 5. Estado observado

```
requisitos: 40 · blockers: 2 · observaciones: 652 · fuentes ilegibles: 0
gate: not_met · evaluación válida · exit 10
```

| Categoría | Cantidad |
|---|---:|
| `machine_pass` | 38 |
| `pending_human` | 1 |
| `machine_fail` | 1 |

### Los 2 blockers, por naturaleza

| Naturaleza | Cantidad | Detalle |
|---|---:|---|
| Owners accountable sin asignar | 0 | los 7 slots usan el alias humano estable `FOUNDER-01` |
| ADR requeridos no listos | 0 | **11 de 11** están ratificados y `ready` |
| Revisión humana independiente | 1 | el Founder no puede contar como segunda mirada; personas distintas siguen pendientes |
| Validador en rojo | 1 | `chk-supply-chain`: procedencia no demostrada |

IMP-017 registra la aceptación del Founder y resuelve el paquete de diez decisiones.
S1-READY sigue `not_met`: no se puede fabricar la revisión independiente ni declarar
SBOM, firma, procedencia o verificación de origen que aún no existen.

---

## 6. Códigos de salida

| Código | Significado |
|---:|---|
| `0` | evaluación válida **y** gate `met` |
| `10` | evaluación válida **y** gate `not_met` ← el resultado de hoy |
| `1` | evaluación **inválida**: contrato inválido, fuente ilegible, check sin ejecutar o ciclo |
| `2` | uso inválido |

Separar `10` de `1` importa: «la herramienta funcionó y el gate no está listo» no es
lo mismo que «la herramienta no pudo decirlo». Y `0` no se fuerza jamás como señal de
conveniencia: significa que todos los requisitos, incluidas las aprobaciones humanas,
están satisfechos en una fuente autoritativa.

---

## 7. Evidencia y frescura

Cada requisito de máquina registra comando, exit code, resultado y versión del
intérprete. Cada fuente registra su digest.

La frescura se mide **por digest, no por reloj**: ningún humano ha decidido una
antigüedad máxima para la evidencia, e inventar un número sería fabricar política.
El contrato declara `max_age_days: null` de forma explícita y el validador rechaza
cualquier valor numérico.

### Checks pesados: declarados, no reejecutados

`evaluate` **no arranca contenedores**. Dos ejecuciones pesadas quedan fuera de su
proceso y se declaran de forma explícita:

| Check | Comando | Estado |
|---|---|---|
| `migration-spike-runtime` | `python -m tools.migration_spike.cli run --suite all` | `declared_not_reexecuted` |
| `mutation-run` | `python -m tools.mutation_harness.cli run` | `declared_not_reexecuted` |

Los digests solo demuestran que los contratos y manifiestos declarados no cambiaron;
**no demuestran que el runtime haya pasado**. El spike PostgreSQL y las mutaciones se
ejecutan en carriles propios de CI. El agregador no convierte frescura de un contrato
en evidencia de ejecución.

---

## 8. Un check en verde no cierra nada

Dos casos que el contrato y las pruebas protegen explícitamente:

- **TM-005 no se cierra porque `chk-supply-chain` pase.** El baseline demuestra pins;
  no demuestra procedencia. `supply-chain.json` mantiene `tm_005.state: open`.
- **ADR-002 no se acepta porque el spike de migraciones pase.** `migration-spike.json`
  mantiene `adr_state: proposed` y `selected_tool: null`.

---

## 9. CLI

```bash
python -m tools.s1_readiness.cli validate
python -m tools.s1_readiness.cli evaluate
python -m tools.s1_readiness.cli explain --gate S1-READY
python -m tools.s1_readiness.cli explain --owner Legal
python -m tools.s1_readiness.cli graph
```

`explain` filtra, pero el filtro es una **vista**: el total canónico viaja siempre en
`canonical_blocker_count`, junto a `filtered_out_count`. Filtrar por owner no puede
hacer desaparecer un blocker del resultado.

`graph` produce el grafo de dependencias entre requisitos, comprobando que sea
acíclico y que ningún requisito apunte a un gate desconocido. Hoy: 40 nodos, 0
aristas, acíclico.

---

## 10. Límites honestos

1. Este agregador no aprueba nada: solo dice qué falta.
2. Un validador en verde acredita un contrato ejecutable, no una decisión humana.
3. No existe una nota agregada, y no se va a añadir: ocultaría el blocker.
4. Filtrar produce una vista, nunca un resultado canónico distinto.
5. No ejecuta contenedores: la evidencia de infraestructura la produce su propio spike.
6. No lee prosa como estado.
7. No escribe `CURRENT_PHASE`, backlog, gates, decisiones ni fichas de tarea.

---

## 11. Qué haría falta para que S1 estuviera listo

En orden de dependencia, no de esfuerzo:

1. **Asignar los siete owners humanos.** Sin personas, ningún gate puede aprobarse, y
   todo lo demás queda esperando.
2. **Resolver las 10 decisiones que sus fuentes declaran bloqueantes de S1.**
3. **Llevar los 11 ADR requeridos a `ready`**, empezando por ADR-002, hoy `blocked`.
4. **Demostrar procedencia de la cadena de suministro** o aceptar el riesgo por escrito.

A-02, L-01/02, DRG-00/01, S-01 y GA-01 permanecen pendientes para sus gates
posteriores; no habilitan datos reales, nube, IA externa, piloto ni venta general.

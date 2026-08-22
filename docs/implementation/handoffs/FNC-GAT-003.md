# Handoff — FNC-GAT-003: agregador ejecutable de readiness S1

| Campo | Valor |
|---|---|
| Tarea | FNC-GAT-003 |
| Estado | **`REVIEW_PENDING`** |
| Base declarada | `48b21d1` — entregada por el Integration Steward, **no verificada** |
| Verificación de la base | No se usó Git en ninguna forma |
| `integration_sha` | `pending_integration_steward` |
| `quality_gate_on_git_index` | `pending_integration_steward` |
| Owner | Integration Steward |
| Revisores independientes | Product, Architecture, Security, Accounting, QA |
| Gate objetivo | **S1-READY — `not_met`**, aceptación `pending_human` |

---

## 1. Rutas creadas

| Ruta | Acción |
|---|---|
| `docs/implementation/s1-readiness.json` | creada — contrato autoritativo |
| `docs/implementation/S1_READINESS_REPORT.md` | creada — documentación |
| `tools/s1_readiness/__init__.py` | creada |
| `tools/s1_readiness/sources.py` | creada — lectura de fuentes estructuradas |
| `tools/s1_readiness/evaluate.py` | creada — agregación fail-closed |
| `tools/s1_readiness/model.py` | creada — validación del contrato |
| `tools/s1_readiness/cli.py` | creada — `validate`/`evaluate`/`explain`/`graph` |
| `tools/s1_readiness/test_validate.py` | creada — 84 pruebas |
| `docs/implementation/handoffs/FNC-GAT-003.md` | este documento |

**No se tocó** `CURRENT_PHASE.md`, backlog, trazabilidad, work graph, gates,
decisiones, ownership, tareas, ADR, CI ni ningún contrato existente. Todas las rutas
reservadas quedan liberadas.

---

## 2. Contrato y decisiones implementadas

- **Agregación conjuntiva fail-closed**: solo `machine_pass` satisface. `pending_human`,
  `not_executed`, `stale_evidence`, `blocked_dependency`, `contradiction` y
  `machine_fail` nunca cuentan.
- **Solo fuentes estructuradas**: 21 modelos JSON más front-matter. El validador
  rechaza una fuente en Markdown narrativo y rechaza invertir la precedencia.
- **Conjuntos dinámicos**: `adr_set` y `decision_set` se descubren, no se copian. Una
  decisión nueva o un ADR requerido nuevo aparecen solos.
- **Contradicciones reportadas, nunca resueltas en silencio.**
- **Frescura por digest, no por reloj**: `max_age_days: null` porque ningún humano ha
  decidido una antigüedad máxima, e inventarla sería fabricar política. El validador
  rechaza cualquier número.
- **`evaluate` no arranca contenedores**; consume evidencia declarada de los checks
  pesados con estado `declared_not_reexecuted`.
- **Códigos de salida estables** que separan «gate no cumplido» de «evaluación
  inválida».
- **Sin nota agregada**, y filtrar produce una vista que conserva el total canónico.

Las 18 invariantes negativas del encargo tienen prueba negativa, más tres
metamórficas.

---

## 3. Comandos exactos y resultado

| Comando | Exit | Resultado |
|---|---:|---|
| `python -m unittest tools.s1_readiness.test_validate` | 0 | **84 pruebas, OK** |
| `python -m tools.s1_readiness.cli validate` | 0 | contrato válido |
| `python -m tools.s1_readiness.cli evaluate` | **10** | evaluación válida, **gate `not_met`** |
| `python -m tools.s1_readiness.cli explain --gate S1-READY` | **10** | 20 blockers canónicos, 11 mostrados, 9 filtrados |
| `python -m tools.s1_readiness.cli graph` | 0 | 49 nodos, 2 aristas, acíclico, sin gates desconocidos |

**Exit 10 es el resultado correcto**, no un fallo de implementación: la herramienta
funcionó y el gate no está cumplido.

---

## 4. Estado S1 observado

```
requisitos: 49 · blockers: 20 · observaciones: 534 · fuentes ilegibles: 0
machine_pass 29 · pending_human 16 · contradiction 3 · machine_fail 1
```

| Naturaleza del blocker | Cantidad |
|---|---:|
| Owners humanos sin asignar (los 7 slots de `CURRENT_PHASE.md`) | 7 |
| Gates de programa sin cumplir (`A-02`, `GA-01`, `L-01`, `L-02`, `S-01`) | 5 |
| Gates en contradicción (`DRG-00`, `DRG-01`) | 2 |
| Decisiones citadas aparte (`UD-A-02`, `UD-L-01`) | 2 |
| ADR requeridos no listos (**11 de 11**) | 1 |
| Decisiones humanas abiertas (**43 de 43**) | 1 |
| Contradicciones sin resolver | 1 |
| Validador en rojo (`chk-supply-chain`) | 1 |

**Ninguna fuente del repositorio registra aceptación humana. No hay un solo owner
nominal asignado.**

---

## 5. Contradicciones detectadas — fuera de scope, no corregidas

| Sujeto | Campo | Valores | Fuentes |
|---|---|---|---|
| `DRG-00` | `owner_role` | `Legal` / `Security` | `docs/privacy/privacy-map.json$.gates[1]` · `docs/domain/lineage-model.json$.gates[1]` |
| `DRG-01` | `owner_role` | `Legal` / `Security` | `docs/privacy/privacy-map.json$.gates[2]` · `docs/domain/lineage-model.json$.gates[2]` |

Ambas rutas son ajenas a esta tarea y no se tocaron. Impacto: mientras dos fuentes
discrepen sobre quién es el owner de un gate de datos, no está definido quién puede
aprobarlo. **Owner de la adjudicación: Integration Steward, con Legal y Security.**

---

## 6. Pruebas negativas y qué demostraron

| Invariante | Degradación | Resultado |
|---|---|---|
| 1 | gate `not_met` con todos los checks en verde | sigue `pending_human`; el gate no se promueve |
| 2 | seis categorías no satisfactorias | ninguna está en `SATISFYING_CATEGORIES` |
| 3 | `security_owner: UNASSIGNED` | `pending_human`; con nombre real pasa a `machine_pass` |
| 4 | `human_acceptance: accepted`, `agent_may_accept: true`, `writes_central_state: true` | `S1R-ACCEPTANCE`, `S1R-AUTHORITY` |
| 5 | fuente `kind: markdown`; precedencia invertida | `S1R-SOURCE-KIND`, `S1R-PRECEDENCE` |
| 6 | dos fuentes con owner distinto para el mismo gate | contradicción reportada con `resolution: pending_human` |
| 7 | módulo `os`, argv string, `; id`, `cwd ../elsewhere` | `S1R-MODULE-ALLOWLIST`, `S1R-ARGV-LIST`, `S1R-ARGV-SHELL`, `S1R-CWD`, y `refused` en ejecución |
| 8 | tope de salida de 64 bytes; exit inesperado; check ausente | `truncated`, `failed`, `not_executed`; ninguno es pass |
| 9 | se retira `chk-privacy` del registro | `S1R-COVERAGE-OMISSION` |
| 9b | se añade una decisión nueva a una fuente sin tocar el registro | pasa de `machine_pass` a `pending_human` sola |
| 10 | ciclo A→B→A; autodependencia; dependencia inexistente | ciclo detectado, `S1R-DEPENDENCY` |
| 11 | evidencia sin `path`, `sha256` o `produced_by` | `S1R-EVIDENCE-FIELDS` |
| 12 | digest de baseline alterado; `max_age_days: 30`; `measured_by: wall_clock` | `stale_evidence`, `S1R-FRESHNESS` |
| 13 | `aggregate_score_as_gate: true` | `S1R-SCORE`; y el score real es `null` |
| 14 | filtro por owner inexistente | 0 mostrados, **20 canónicos siguen reportados** |
| 15 | búsqueda de entorno, secretos y patrón de NIT en las cuatro salidas | ninguno aparece |
| 16 | `evaluate` sobre el repositorio real | `not_met` / `pending_human`, exit 10 |
| 17 | `chk-supply-chain` en verde | `tm_005.state` sigue `open` |
| 18 | spike DB 12/12 en verde | `adr_state` sigue `proposed`; `adr_set` no pasa |

**Metamórficas:** invertir fuentes y requisitos no cambia el veredicto ni los conteos;
añadir un blocker elegible lo cambia de 0 a 1; dos evaluaciones consecutivas son
idénticas.

---

## 7. Hallazgo propio corregido durante la ejecución

El lector de front-matter rechazaba `docs/implementation/tasks/FNC-PRV-001.md` porque
usa una lista de bloque (`file_scope:` seguido de `  - item`). Eso invalidaba la
evaluación entera por una clave que ni siquiera se usa. Se extendió el subconjunto
soportado para leer listas de bloque —una forma sin ambigüedad— manteniendo el fallo
cerrado para mappings anidados. Ampliar el subconjunto es honesto; adivinar no lo
sería.

---

## 8. Riesgos y gaps que permanecen

- **20 blockers**, todos con owner y explicación accionable.
- **La cobertura crítica es declarativa**: `critical_coverage` se compara con lo que
  los checks dicen cubrir. Si un check mintiera sobre su `covers`, la omisión no se
  detectaría. Mitigado en parte porque cada check es un módulo real que se ejecuta.
- **El agregador depende de que las fuentes declaren sus gates bajo la clave
  declarada.** Una fuente nueva con una clave nueva no se descubre sola: hay que
  añadirla a `sources`. Es una decisión consciente —descubrir claves arbitrarias
  produciría falsos positivos— y queda como riesgo conocido.
- **43 decisiones abiertas** es un número grande. Parte puede no bloquear S1; hoy el
  agregador las cuenta todas, fail-closed. Reclasificarlas es trabajo humano.

---

## 9. Rollback

Eliminar `tools/s1_readiness/`, `docs/implementation/s1-readiness.json` y
`docs/implementation/S1_READINESS_REPORT.md`. No modifica nada ajeno; el rollback es
total. Dependencia entrante: el check `test-unit-new` de FNC-PLT-007 referencia
`tools.s1_readiness.test_validate`; si se revierte, retirar esa referencia.

---

## 10. Pasos para el Integration Steward

1. **Indexar** las rutas de §1.
2. **Ejecutar el quality gate sobre el índice Git.** No se ejecutó aquí.
3. **CI**: si se añade, tratar `exit 10` como informativo y `exit 1` como fallo real.
   Confundirlos convertiría «S1 no está listo» en «la herramienta se rompió».
4. **Adjudicar las dos contradicciones** de `DRG-00` y `DRG-01` con Legal y Security, y
   corregir la fuente que quede en minoría.
5. **Asignar los siete owners humanos** en `CURRENT_PHASE.md`. Es el blocker raíz: sin
   personas, ningún gate puede aprobarse.
6. **Catálogo y trazabilidad**: `s1-readiness.json` no declara `required_tests`, así
   que no introduce IDs ni drift.
7. **Digests golden/mutation**: ninguno deriva de este cambio. Sí conviene saber que
   `evidence_baseline` fija por digest `migration-spike.json`,
   `spikes/FNC-DB-002/MANIFEST.json`, `supply-chain.json` y `mutation-harness.json`:
   cualquier cambio en ellos deja la evidencia `stale_evidence` hasta reejecutar su
   productor.
8. **Actualizar `work-graph.json`**: `human_gates[]` cubre FNC-GOV-001, FNC-GAT-001 y
   FNC-GAT-002 pero no FNC-GAT-003. No se corrigió por ser ruta protegida.
9. **Liberar reservas** de FNC-GAT-003.

Estado final: **`REVIEW_PENDING`**, gate **`not_met`**, aceptación `pending_human`. No
se declara aceptación, integración, head SHA, CI remoto ni revisión humana
inexistentes. Ningún check en verde cierra TM-005 ni acepta ADR-002.

---

## 11. Entrega conjunta SUP → DB → PLT → GAT

### Resumen de las cuatro tareas

| Tarea | Entrega | Estado | Resultado medido |
|---|---|---|---|
| **FNC-SUP-001** | baseline de cadena de suministro | `REVIEW_PENDING` | 26 componentes, **0 defectos de pin**, 4 gaps de procedencia bloquean DRG-00 |
| **FNC-DB-002** | spike de invariantes de migración | `REVIEW_PENDING` | **12/12 contra PostgreSQL 17.11 real**, sin residuo, ADR-002 sigue `proposed` |
| **FNC-PLT-007** | CLI de desarrollo | `REVIEW_PENDING` | 25 checks, 24 pass, 1 gap declarado, 0 fallos inesperados |
| **FNC-GAT-003** | agregador de readiness S1 | `REVIEW_PENDING` | **S1-READY `not_met`**, 20 blockers con owner |

### Pruebas y comandos

| Suite | Pruebas |
|---|---:|
| `tools.supply_chain.test_validate` | 68 |
| `tools.migration_spike.test_validate` | 105 |
| `tools.dev_cli.test_cli` | 78 |
| `tools.s1_readiness.test_validate` | 84 |
| **Total nuevo** | **335** (mínimo exigido: 140) |
| Suite completa del repositorio (33 módulos) | **1055, OK** |

Los 21 comandos de la verificación obligatoria se ejecutaron en el orden del encargo.
Exits distintos de cero y por qué: `supply_chain validate/report` = 1 (gaps de
procedencia), `dev_cli validate --group all` = 1 (el mismo gap), `dev_cli stack status`
= 3 (Docker no responde al binario directo), `s1_readiness evaluate/explain` = 10
(gate no cumplido, evaluación válida). Ninguno es un fallo de implementación.

**`tools.quality_gate.cli` no se ejecutó y no se declara exitoso**: opera sobre el
índice Git y aquí no se usó Git. Queda explícitamente pendiente del Integration
Steward.

### Resultado real del spike Docker

Docker estaba disponible **dentro de WSL** (29.7.2, compose v5.5.0). La imagen
PostgreSQL fijada por digest ya estaba en caché, así que no se descargó nada nuevo.
Los 12 casos pasaron contra PostgreSQL 17.11 real y la limpieza dejó 0 contenedores,
0 volúmenes y 0 redes. El proyecto `fincilia-local` no se levantó en ningún momento.

### Cómo encajan

```
SUP-001 ──pins y procedencia──┐
DB-002  ──invariantes de esquema──┤
                                  ├──► GAT-003 agrega y bloquea
PLT-007 ──compone y diagnostica───┘
```

- **PLT-007 consume SUP-001 y DB-002** como checks allowlisted (`security-supply-chain`,
  `data-migration-spike`).
- **GAT-003 consume los tres**: `chk-supply-chain` y `chk-migration-spike` como checks
  de máquina, `developer-cli.json` y `supply-chain.json` como fuentes de gates y
  decisiones, y `migration-spike.json` más su manifiesto como `evidence_baseline`.
- **Ninguna tarea escribe en el ámbito de otra.** Los cuatro contratos declaran
  `human_acceptance: pending` y todos sus gates `not_met`.

### Hallazgos fuera de scope, consolidados

| # | Ruta | Impacto | Owner |
|---|---|---|---|
| 1 | `docs/privacy/privacy-map.json` vs `docs/domain/lineage-model.json` | `DRG-00` y `DRG-01` declaran owner distinto: no está definido quién puede aprobarlos | Integration Steward + Legal + Security |
| 2 | `.github/dependabot.yml` | `spikes/FNC-PLT-005/api`, `spikes/FNC-PLT-005` e `infra/local` sin vigilancia de actualizaciones | Platform |
| 3 | `.github/workflows/ci.yml` | `runs-on: ubuntu-24.04` no es un artefacto inmutable; queda como gap, no como pin | Platform |
| 4 | `docs/implementation/work-graph.json` | `human_gates[]` no incluye FNC-GAT-003 | Integration Steward |
| 5 | `docs/database/migration-tooling.json` | `spike_matrix` sigue con los ocho casos en `not_run`; seis ya tienen evidencia real en FNC-DB-002 | Database Migration Owner |

Ninguno se corrigió: todos caen en rutas protegidas o ajenas.

### Orden de integración

1. **SUP-001** — no depende de nada nuevo.
2. **DB-002** — independiente de SUP-001, pero su manifiesto entra en el
   `evidence_baseline` de GAT-003, así que conviene antes.
3. **PLT-007** — referencia módulos de SUP-001 y DB-002; integrarla antes dejaría dos
   checks apuntando a módulos inexistentes.
4. **GAT-003** — referencia los tres anteriores; va última.

Tras cada paso: quality gate sobre el índice, y al final
`python -m tools.test_catalog.cli validate` para confirmar que ninguno de los cuatro
introdujo drift de catálogo.

### Anti-promesa final

Cuatro suites en verde y 1055 pruebas pasando **no** significan que S1 esté cerca. El
propio agregador lo dice con su exit 10: faltan siete owners humanos, cinco gates,
once ADR, cuarenta y tres decisiones y dos contradicciones por adjudicar. Ninguna de
esas cosas la puede firmar un agente.

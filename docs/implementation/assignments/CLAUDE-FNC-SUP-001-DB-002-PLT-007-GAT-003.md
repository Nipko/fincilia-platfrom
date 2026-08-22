# Encargo principal Claude — SUP-001 + DB-002 + PLT-007 + GAT-003

## 0. Misión y forma de ejecución

Actúa como principal dev durante una ejecución larga de cuatro tareas concatenadas. No
te detengas entre tareas, no solicites confirmación y no entregues resultados parciales
como si fueran finales. Ejecuta en este orden:

1. `FNC-SUP-001`: baseline ejecutable de cadena de suministro.
2. `FNC-DB-002`: spike real de invariantes de migración sobre PostgreSQL efímero.
3. `FNC-PLT-007`: CLI segura que compone diagnósticos y comandos existentes.
4. `FNC-GAT-003`: agregador fail-closed de readiness S1.

Al terminar cada etapa corre sus pruebas, pero continúa inmediatamente con la siguiente.
Al final ejecuta las cuatro suites juntas, sus CLIs y los validadores integrados que
consumen. Corrige toda regresión dentro de tus rutas y entrega cuatro handoffs separados.

El resultado máximo es `REVIEW_PENDING`. No aceptes ADR, gates, decisiones, riesgo
residual, región, proveedor, presupuesto, licencia ni procedencia. Si algo exige decisión
humana, regístralo con owner y gate, mantenlo fail-closed y continúa.

## 1. Base, modalidad y prohibiciones

- Base exacta integrada: `48b21d1`.
- No uses Git de ninguna forma: no `status`, `diff`, `log`, `show`, `add`, `commit`,
  `checkout`, lectura del índice ni cálculo de base/head.
- El filesystem es compartido; escribe solo en las rutas reservadas de §3.
- Datos exclusivamente sintéticos. No copies documentos, extractos, PII, credenciales,
  tokens, valores de `.env`, dumps o payloads financieros.
- Cero acceso a proveedores y cero cambios cloud.
- No instales dependencias Python/npm. Usa biblioteca estándar Python 3.11+.
- Docker se usa únicamente en el spike DB dentro de su Compose aislado.
- No descargues imágenes nuevas deliberadamente. Reutiliza la referencia PostgreSQL
  fijada por digest que ya existe en `infra/local/compose.yaml`.
- No uses `shell=True`, `eval`, `exec`, scripts recibidos desde JSON, comandos en string,
  regex de reemplazo libre ni variables de entorno como comandos.
- No uses `docker compose down --volumes` fuera del proyecto exacto del spike. La CLI de
  desarrollo no implementa purga ni borrado de datos.
- No edites archivos centrales o protegidos: CI, `CURRENT_PHASE.md`, backlog,
  trazabilidad, work graph, gates, decisions, ownership, tareas, assignment, ADR,
  contratos existentes, Compose existente, locks o migraciones productivas.
- No modifiques QA-002..005, golden harness, mutation harness, catálogo ni validadores
  existentes. Consúmelos solo lectura.
- Si un contrato externo está mal, informa ruta, regla, impacto y owner. No lo “arregles”
  fuera del alcance.

## 2. Lectura obligatoria completa

Antes de escribir, lee por completo:

1. `AGENTS.md` y `CURRENT_PHASE.md`.
2. Las cuatro fichas `FNC-SUP-001`, `FNC-DB-002`, `FNC-PLT-007`, `FNC-GAT-003`.
3. `docs/implementation/DEFINITION_OF_READY.md` y `DEFINITION_OF_DONE.md`.
4. `docs/implementation/OWNERSHIP.md`, `GATES.md` y `DECISION_LOG.md`.
5. `docs/implementation/TRACEABILITY.md` y `BACKLOG_PHASE_0.md`.
6. `docs/security/THREAT_MODEL.md`, `threat-model.json` y `DATA_CLASSIFICATION.md`.
7. `docs/testing/TEST_STRATEGY.md`, `test-strategy.json`, `TEST_CATALOG.md`,
   `GOLDEN_HARNESS.md`, `MUTATION_HARNESS.md` y sus JSON.
8. `docs/testing/CI_QUALITY_GATE.md`, `.github/workflows/ci.yml` y
   `.github/dependabot.yml`, solo lectura.
9. `docs/platform/LOCAL_DEVELOPMENT.md`, `runtime-config.json`,
   `docs/platform/MONOREPO_SCAFFOLD.md` e `infra/local/compose.yaml`.
10. `docs/database/MIGRATION_TOOLING.md`, `migration-tooling.json`, ADR-002 y ADR-021.
11. `docs/architecture/ADR_READINESS.md`, `adr-readiness.json`, ADR-001..023.
12. Todos los `*-model.json`, validators y CLIs existentes bajo `tools/`, dinámicamente
    con `rg --files`; no mantengas una lista paralela obsoleta.

Confirma internamente: cuatro IDs, base, rutas, datos, dependencias, owners y comandos.

## 3. Rutas exclusivas

### FNC-SUP-001

- `docs/security/SUPPLY_CHAIN_BASELINE.md`
- `docs/security/supply-chain.json`
- `tools/supply_chain/**`
- `docs/implementation/handoffs/FNC-SUP-001.md`

### FNC-DB-002

- `docs/database/MIGRATION_SPIKE.md`
- `docs/database/migration-spike.json`
- `spikes/FNC-DB-002/**`
- `tools/migration_spike/**`
- `docs/implementation/handoffs/FNC-DB-002.md`

### FNC-PLT-007

- `docs/platform/DEVELOPER_CLI.md`
- `docs/platform/developer-cli.json`
- `tools/dev_cli/**`
- `docs/implementation/handoffs/FNC-PLT-007.md`

### FNC-GAT-003

- `docs/implementation/S1_READINESS_REPORT.md`
- `docs/implementation/s1-readiness.json`
- `tools/s1_readiness/**`
- `docs/implementation/handoffs/FNC-GAT-003.md`

No crees archivos en ninguna otra ruta.

---

## 4. Etapa A — FNC-SUP-001: cadena de suministro ejecutable

### 4.1 Objetivo

Crear un contrato y un validador offline que respondan, con evidencia reproducible:

- qué GitHub Actions existen y si están fijadas a SHA completo;
- qué imágenes OCI se declaran y si están fijadas por digest;
- qué runtimes/versions influyen en resultados;
- qué manifests y lockfiles existen y cuál es su alcance;
- qué fuentes no están inventariadas;
- qué evidencia falta para SBOM, firma, provenance y verificación de origen.

No dupliques el secret scanner ni prometas que un hash acredita al autor. El digest prueba
identidad del artefacto observado; la procedencia requiere verificación independiente.

### 4.2 Contrato `supply-chain.json`

Debe incluir como mínimo:

- schema, task, status `review_pending`, `synthetic_only`, human acceptance pending;
- tipos de componente allowlisted: action, image, runtime, package manifest, lockfile,
  generated artifact y external build service;
- reglas de descubrimiento, normalización y exclusión;
- política de pins: action SHA-40, OCI `@sha256:<64>`, runtime exacto;
- relación manifest ↔ lockfile y alcance por workspace/spike;
- estados de evidencia: observed, digest_pinned, source_verified_pending,
  sbom_pending, provenance_pending, signature_pending;
- controles para lifecycle scripts, scripts de instalación y dependencias no lockeadas;
- ownership/review, riesgo, gate y evidencia esperada por finding;
- catálogo de excepciones con expiración y aprobación humana, inicialmente vacío;
- gaps TM-005 que siguen bloqueados;
- anti-promesas explícitas.

No copies una lista manual completa de archivos si puede descubrirse con globs exactos.
Todo resultado debe incluir ruta canónica y digest de la fuente escaneada.

### 4.3 CLI

Implementa:

```text
python -m tools.supply_chain.cli discover
python -m tools.supply_chain.cli validate
python -m tools.supply_chain.cli report
```

Requisitos:

- JSON ordenado a stdout; errores operativos a stderr;
- root/model inyectables y confinados al árbol;
- sin red, reloj, hostname, Git ni entorno completo;
- symlinks y path traversal rechazados;
- no ejecutar acciones, imágenes, scripts o packages descubiertos;
- `validate` falla solo según severidad declarada, no por un score agregado;
- `report` muestra blockers y gaps por riesgo/owner/gate.

### 4.4 Negativas mínimas

1. Action con tag, branch, SHA corto o referencia vacía.
2. Imagen sin digest, con `latest` o digest mal formado.
3. Runtime `current`, `stable`, `main` o rango abierto.
4. Manifest npm sin lockfile o lockfile fuera de alcance.
5. Lockfile huérfano o duplicado incompatible.
6. `npm install`/`pip install` no acotado declarado como reproducible.
7. Lifecycle scripts permitidos silenciosamente en CI sensible.
8. Componente externo sin owner, source, risk o gate.
9. Digest confundido con firma/procedencia aceptada.
10. SBOM/provenance/signature marcados completos sin evidencia verificable.
11. Excepción sin owner, revisor, motivo, expiración y gate.
12. Archivo bajo vendor/cache contado como fuente propia.
13. Path absoluto, traversal interno normalizable o symlink externo.
14. Orden del filesystem cambia inventario/digest.
15. Resultado filtra variables, secretos o contenido de archivos sensibles.
16. Agente marca TM-005 resuelto.

Incluye pruebas metamórficas: reordenar YAML/JSON sin cambiar referencias no altera el
inventario semántico; añadir una nueva action o imagen elegible sí aparece.

---

## 5. Etapa B — FNC-DB-002: spike de migraciones

### 5.1 Alcance exacto

Este spike prueba invariantes, no escoge herramienta productiva. No modifica
`db/migrations`, ADR-002, `infra/local`, roles productivos ni CI.

Construye un laboratorio autocontenido en `spikes/FNC-DB-002` con:

- Compose con nombre de proyecto explícito y PostgreSQL 17 fijado por el mismo digest ya
  adjudicado en infraestructura local;
- bind solo a `127.0.0.1` si expone puerto; preferiblemente sin puerto host;
- healthcheck;
- datos, roles y esquemas exclusivamente sintéticos;
- migraciones de laboratorio versionadas y manifest con SHA-256;
- rol bootstrap, rol migrator y rol runtime separados;
- history table del spike con versión, nombre, checksum, applied_at del servidor y estado;
- advisory lock o primitiva PostgreSQL para serializar migradores;
- transacción por migración y rollback ante fallo;
- prohibición de `SUPERUSER`, `BYPASSRLS`, `CREATEDB` y `CREATEROLE` para runtime;
- `FORCE ROW LEVEL SECURITY` sobre tabla company-scoped sintética;
- ningún `down` destructivo o rollback histórico automático.

El runner puede usar `subprocess` solo con argv fijo/allowlisted y `shell=False`. Para SQL,
usa `psql` dentro del contenedor/lab; no añadas driver Python.

### 5.2 Contrato `migration-spike.json`

Declara:

- hipótesis y límites;
- versiones/digests exactos;
- manifest de migraciones y checksums;
- estados de ejecución;
- invariantes, casos y resultados esperados;
- owners/reviewers/gates;
- evidencia machine-readable permitida;
- estrategia expand/contract y compatibilidad N/N+1 como política, no prueba absoluta;
- decisión de tooling aún `pending_human`/ADR-002;
- limpieza confinada al Compose project exacto;
- anti-promesas.

### 5.3 Pruebas PostgreSQL obligatorias

Ejecuta, si Docker está disponible:

1. **blank**: base vacía llega al estado esperado.
2. **replay**: segunda ejecución es no-op y no duplica history.
3. **tamper**: modificar una migración ya aplicada falla por checksum antes de ejecutar.
4. **partial failure**: error a mitad de migración no deja objetos parciales ni history ok.
5. **concurrency**: dos migradores concurrentes producen una sola aplicación.
6. **runtime denial**: runtime no crea/alter/drop schema ni escribe history.
7. **privileges**: runtime/migrator no son superuser ni BYPASSRLS; runtime no es owner.
8. **RLS**: A no lee/escribe B y contexto ausente falla cerrado.
9. **FORCE RLS**: tablas sensibles lo conservan.
10. **checksum order**: orden de directorio no cambia plan canónico.
11. **unknown migration**: versión duplicada o hueco prohibido se rechaza.
12. **cleanup scope**: el runner nunca apunta a un project/volume ajeno.

Si Docker no está disponible, no simules resultados: corre validación estructural, marca
evidencia runtime `not_executed`, handoff `PARTIAL` y describe el comando exacto pendiente.

### 5.4 CLI

```text
python -m tools.migration_spike.cli validate
python -m tools.migration_spike.cli plan
python -m tools.migration_spike.cli run --suite all
python -m tools.migration_spike.cli report
```

`plan` jamás muta. `run` solo opera el laboratorio exacto. `report` no inventa evidencia
si no hubo ejecución. Ningún comando borra volúmenes por defecto.

### 5.5 Negativas unitarias

Incluye al menos: digest OCI flotante, SQL fuera de rutas, checksum inválido, versión
duplicada, gap, archivo no manifestado, manifest que apunta fuera, comando shell/string,
project name alterado, volumen externo, rol privilegiado, runtime owner, RLS omitida,
history mutable por runtime, migración sin transacción, `DROP` destructivo no aprobado,
aceptación automática de ADR y evidencia runtime fabricada.

---

## 6. Etapa C — FNC-PLT-007: CLI de desarrollo

### 6.1 Propósito

Reducir comandos manuales sin crear una autoridad paralela. La CLI solo compone contratos
existentes mediante un registro explícito, argv fijo y resultados observables.

### 6.2 Comandos

Implementa como mínimo:

```text
python -m tools.dev_cli.cli doctor
python -m tools.dev_cli.cli validate [--group core|security|data|qa|all]
python -m tools.dev_cli.cli test [--group unit|golden|mutation|all]
python -m tools.dev_cli.cli stack status
python -m tools.dev_cli.cli stack up
python -m tools.dev_cli.cli stack down
python -m tools.dev_cli.cli evidence summary
```

Opcional: `--format json|text`, con JSON como representación canónica. No implementes
instalación automática, actualización, purge, reset, seed real, migrations productivas,
cloud, secretos o modificación de configuración.

### 6.3 Contrato `developer-cli.json`

Debe declarar:

- comandos, grupos, argv exacto, cwd relativo y timeout/output máximos;
- módulos Python allowlisted y Compose project allowlisted;
- dependencias requeridas/opcionales: Python, Docker CLI/daemon, Compose, Node/WSL solo
  cuando una suite lo necesita;
- códigos de salida: ok, check_failed, dependency_missing, timeout, invalid_usage;
- política de entorno mínima; no heredar proxies/tokens/credenciales;
- clasificación de cada comando como read_only o local_reversible;
- locks de proceso para `stack up/down`;
- contrato de degradación: doctor sigue funcionando sin Docker;
- datos synthetic-only y puertos localhost;
- owners/gates/evidence y anti-promesas.

### 6.4 Reglas operativas

- Ejecuta subprocess con lista argv, `shell=False`, cwd confinado y env allowlist.
- Nunca obtiene comandos desde el usuario o JSON sin cruzar allowlist exacto.
- No imprime `.env`, variables completas, stdout sensible o paths de usuario innecesarios.
- Acota stdout/stderr; truncamiento hace fallar la comprobación.
- `validate all` conserva el resultado individual; no oculta fallo con promedio.
- `test mutation` puede ser largo y debe tener timeout explícito.
- `stack status` es read-only.
- `stack up` usa el Compose local existente sin cambiarlo.
- `stack down` no incluye `--volumes` ni `--remove-orphans` si eso pudiera afectar otro
  project; usa el nombre/project/cwd exactos del contrato.
- Reentrada concurrente se rechaza o serializa con lock local seguro.
- La CLI nunca cambia gate/status/documentos.

### 6.5 Negativas mínimas

1. Módulo, runtime, cwd o Compose no allowlisted.
2. Argv como string o presencia de metacaracteres de shell.
3. `shell=True`, eval/exec o expansión arbitraria.
4. Path absoluto, `..` interno o symlink externo.
5. Env hereda token/proxy/secret.
6. Output truncado cuenta como PASS.
7. Timeout/skipped/dependency missing cuenta como PASS.
8. `validate all` pierde el check que falló.
9. `stack down` añade `--volumes`, wildcard o project externo.
10. Dos stacks mutadores corren concurrentes sin lock.
11. Doctor exige Docker para checks puramente Python.
12. Evidencia incluye payload, env completo o secreto sintético con forma real.
13. Comando marca S1/DRG como met.
14. JSON/proceso modifica su propio expected output.
15. Orden de registro cambia digest/reporte.
16. Herramienta ausente provoca traceback en vez de diagnóstico estable.

Usa dobles únicamente en unit tests de la capa de proceso. No declares esos tests como
evidencia de integración Docker.

---

## 7. Etapa D — FNC-GAT-003: readiness S1 fail-closed

### 7.1 Problema

Hoy existen muchos contratos válidos y muchas decisiones humanas pendientes. Un validador
verde no equivale a S1 aceptado. El agregador debe mostrar ambas dimensiones sin permitir
que un agente convierta “ejecutable” en “aprobado”.

### 7.2 Contrato `s1-readiness.json`

Incluye:

- esquema, task, status, synthetic-only y gate objetivo;
- fuentes estructuradas de verdad y precedence;
- registro explícito de checks machine y comandos allowlisted;
- decisiones humanas requeridas, roles nominales requeridos y estado observado;
- gates DRG-00, DRG-01, L-01/L-02, ADR bloqueantes y su relación con S1;
- categorías: machine_pass, machine_fail, not_executed, pending_human,
  blocked_dependency, stale_evidence, contradiction;
- regla: solo una aprobación humana en fuente autoritativa puede satisfacer su requisito;
- evidencia con digest de fuente, comando, versión, resultado y freshness policy sin
  inventar duración numérica si no existe decisión;
- agregación conjuntiva fail-closed: unknown/pending/stale no cuenta como met;
- owners/reviewers y explicación por blocker;
- estado inicial `not_met`, acceptance `pending_human`;
- anti-promesas.

No copies resultados actuales como verdades estáticas. Descubre tareas/gates/decisiones
desde fuentes estructuradas y ejecuta checks desde allowlist. Si dos fuentes se contradicen,
reporta contradicción; no elijas silenciosamente.

### 7.3 CLI

```text
python -m tools.s1_readiness.cli validate
python -m tools.s1_readiness.cli evaluate
python -m tools.s1_readiness.cli explain [--owner ROLE] [--gate GATE]
python -m tools.s1_readiness.cli graph
```

- `validate`: estructura del contrato/registro.
- `evaluate`: ejecuta checks allowlisted y calcula reporte determinista.
- `explain`: blockers accionables sin payload sensible.
- `graph`: dependencias machine-readable sin ciclos.

El exit de `evaluate` debe distinguir “herramienta funcionó y gate not_met” de “evaluación
inválida”. Define códigos estables; no fuerces exit 0 como señal de gate aprobado.

### 7.4 Checks y decisiones que debe componer

Como mínimo:

- work graph y catálogo;
- arquitectura/ADR readiness;
- canonical, completeness, idempotency, lineage y cross-contract;
- DFD, privacy, threat, region/transmission;
- runtime config, workspace, local stack, migration readiness/spike;
- quality strategy, golden harness, mutation harness;
- research protocol, provider evaluation, brand clearance y budget;
- supply-chain baseline;
- owners/RACI, Legal/Privacy, Accounting, Security, Product y Founder pendientes.

No ejecutes Docker dentro de `evaluate` por defecto. Consume evidencia declarada del spike
y marca `not_executed/stale` cuando corresponda. Un modo explícito futuro puede ejecutar
checks pesados, pero no lo implementes aquí.

### 7.5 Negativas mínimas

1. Machine pass promueve gate sin aprobación humana.
2. Pending/unknown/stale se interpreta como met.
3. Falta de owner/reviewer permite aprobación.
4. Agente escribe acceptance accepted.
5. Fuente narrativa suplanta fuente estructurada.
6. Dos fuentes contradictorias se resuelven silenciosamente.
7. Check no allowlisted, argv string, shell o cwd externo.
8. Timeout, truncamiento, skipped o exit inesperado cuenta como pass.
9. Check crítico omitido del registro dinámico.
10. Dependencia cíclica o gate desconocido.
11. Evidencia sin digest/version/comando/resultado.
12. Evidencia vieja sin política se considera vigente.
13. Conteo/score global oculta un blocker.
14. Filtro por owner/gate elimina blockers del resultado canónico.
15. Output incluye variables, secretos, raw payload o PII.
16. Estado actual del repo se reporta S1 met.
17. TM-005 se cierra solo por el validador supply-chain.
18. ADR-002 se acepta solo porque el spike DB pasó.

Pruebas metamórficas: reordenar fuentes/checks no cambia veredicto; añadir un blocker
elegible sí cambia el reporte; quitar un check crítico se detecta como omisión, no como
mejora.

---

## 8. Calidad transversal y cantidad de pruebas

Cada herramienta debe tener:

- `__init__.py`, módulo de modelo/registry, validator, CLI y tests;
- solo biblioteca estándar;
- dataclasses/errores tipados cuando ayude;
- funciones puras para validación y root/model inyectables;
- salida determinista y ordenada;
- prueba positiva contra el contrato real;
- pruebas negativas que demuestren que cada regla muerde;
- al menos una prueba metamórfica y una prueba de determinismo;
- escaneo de source que prohíba red, reloj, random, shell y entorno completo;
- cero TODO/FIXME sin ID FNC.

Objetivo mínimo conjunto: **140 pruebas unitarias nuevas** entre las cuatro tareas, sin
contar integración Docker. No infles el número con asserts duplicados; cada caso debe
proteger una invariante o una variante de plataforma relevante.

Cuando una herramienta ejecute subprocess, prueba por separado:

- construcción de argv/env/cwd;
- timeout;
- output cap/truncamiento;
- exit codes;
- ausencia de mutación del árbol fuente;
- path containment;
- mensajes seguros.

## 9. Verificación obligatoria, en orden

### 9.1 Etapa A

```text
python -m unittest tools.supply_chain.test_validate -v
python -m tools.supply_chain.cli discover
python -m tools.supply_chain.cli validate
python -m tools.supply_chain.cli report
```

### 9.2 Etapa B

```text
python -m unittest tools.migration_spike.test_validate -v
python -m tools.migration_spike.cli validate
python -m tools.migration_spike.cli plan
python -m tools.migration_spike.cli run --suite all
python -m tools.migration_spike.cli report
```

Antes del run Docker, valida el Compose. Al terminar, elimina únicamente contenedores y
recursos efímeros del project exacto del spike. Documenta cada exit y si Docker no estaba
disponible.

### 9.3 Etapa C

```text
python -m unittest tools.dev_cli.test_cli -v
python -m tools.dev_cli.cli doctor
python -m tools.dev_cli.cli validate --group all
python -m tools.dev_cli.cli evidence summary
python -m tools.dev_cli.cli stack status
```

No ejecutes `stack down` contra un entorno que no levantaste tú. Sus semánticas se prueban
con dobles y, si levantas stack para integración, solo contra el project exacto declarado.

### 9.4 Etapa D

```text
python -m unittest tools.s1_readiness.test_validate -v
python -m tools.s1_readiness.cli validate
python -m tools.s1_readiness.cli evaluate
python -m tools.s1_readiness.cli explain --gate S1-READY
python -m tools.s1_readiness.cli graph
```

`evaluate` debe mostrar `not_met`; ese veredicto de gate puede usar un exit específico y
no se reporta como falla de implementación.

### 9.5 Regresión final

```text
python -m unittest tools.supply_chain.test_validate tools.migration_spike.test_validate tools.dev_cli.test_cli tools.s1_readiness.test_validate -v
python -m tools.test_catalog.cli validate
python -m tools.golden_harness.cli verify
python -m tools.mutation_harness.cli verify
python -m tools.work_graph.validate
```

No ejecutes `tools.quality_gate.cli`: opera sobre el índice Git y tú no usas Git. Déjalo
explícitamente pendiente al Integration Steward.

## 10. Handoffs obligatorios

Cada handoff debe incluir:

1. ID, base declarada no verificada y estado `REVIEW_PENDING` o `PARTIAL`.
2. Rutas creadas/modificadas y confirmación de no tocar otras.
3. Contrato y decisiones implementadas.
4. Comandos exactos, exit codes y conteos.
5. Para DB: evidencia Docker real o `not_executed`, nunca simulada.
6. Pruebas negativas/mutantes manuales y qué reglas demostraron.
7. Hallazgos externos con ruta, regla, impacto y owner.
8. Riesgos/gaps que permanecen y gate bloqueado.
9. Rollback por ruta.
10. Instrucciones al Integration Steward: orden de indexación, CI, catálogo, trazabilidad,
    digests golden/mutation que puedan derivar y revisiones humanas.

Entrega final conjunta:

- resumen de las cuatro tareas;
- tabla de pruebas y comandos;
- resultado real del spike Docker;
- estado S1 observado;
- hallazgos fuera de scope;
- instrucciones de integración en orden `SUP → DB → PLT → GAT`.

No marques ninguna tarea `DONE`, no modifiques rutas centrales y no confundas “suite
verde” con aceptación del producto.

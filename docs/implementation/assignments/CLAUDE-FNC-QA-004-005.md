# Encargo principal Claude — FNC-QA-004 + FNC-QA-005

## Misión

Actúa como principal dev de QA durante una ejecución larga y concatenada. Implementa
primero FNC-QA-004 y luego FNC-QA-005. Después ejecuta ambas suites juntas, corrige todas
las regresiones dentro de tus rutas y entrega dos handoffs independientes.

No te detengas entre etapas ni solicites confirmación. Cuando una decisión corresponda a
un humano, déjala `pending_human`, bloquea fail-closed lo que dependa de ella y continúa.
El estado final máximo es `REVIEW_PENDING`; no aceptes gates, ADR, riesgos residuales ni
decisiones humanas.

## Base, coordinación y límites

- Base exacta entregada por Integration Steward: `6e23c04`.
- No uses Git de ninguna forma: no `status`, `diff`, `log`, `show`, `add`, `commit`,
  `checkout`, lectura del índice ni cálculo de supuestas bases/heads.
- El filesystem es compartido. Edita únicamente las rutas reservadas por FNC-QA-004/005.
- No edites `TEST_CATALOG.md`, `.github/workflows/ci.yml`, `CURRENT_PHASE.md`, backlog,
  trazabilidad, grafo de trabajo, decisiones, ADR, tareas, contratos ni herramientas existentes.
- No edites FNC-QA-002/003: consúmelos solo como contratos ya integrados.
- Datos exclusivamente sintéticos; cero red, conectores, credenciales o documentos reales.
- Biblioteca estándar de Python. No añadas dependencias.
- Si una ruta o contrato externo contradice este encargo, reporta ruta/ID/impacto/owner;
  no lo corrijas fuera del scope.

## Rutas exclusivas

FNC-QA-004:

- `docs/testing/TEST_CATALOG_MODEL.md`
- `docs/testing/test-catalog-model.json`
- `tools/test_catalog/**`
- `docs/implementation/handoffs/FNC-QA-004.md`

FNC-QA-005:

- `docs/testing/MUTATION_HARNESS.md`
- `docs/testing/mutation-harness.json`
- `tools/mutation_harness/**`
- `tests/golden/mutations/**`
- `docs/implementation/handoffs/FNC-QA-005.md`

No crees archivos en ninguna otra ruta.

## Lectura obligatoria completa antes de escribir

1. `AGENTS.md`
2. `CURRENT_PHASE.md`
3. `docs/implementation/tasks/FNC-QA-004.md`
4. `docs/implementation/tasks/FNC-QA-005.md`
5. `docs/implementation/DEFINITION_OF_READY.md`
6. `docs/implementation/DEFINITION_OF_DONE.md`
7. `docs/implementation/OWNERSHIP.md`
8. `docs/testing/TEST_STRATEGY.md`
9. `docs/testing/test-strategy.json`
10. `docs/testing/TEST_CATALOG.md`
11. `docs/testing/GOLDEN_HARNESS.md`
12. `docs/testing/golden-harness.json`
13. `docs/testing/SYNTHETIC_DATA_POLICY.md`
14. `docs/implementation/TRACEABILITY.md`
15. `docs/implementation/handoffs/FNC-QA-002.md`
16. `docs/implementation/handoffs/FNC-QA-003.md`
17. todos los `*-model.json`, contratos JSON y manifests bajo `docs/` y `tests/golden/`
18. todos los `test_*.py` y validadores bajo `tools/`, solo lectura
19. `.github/workflows/ci.yml`, solo lectura

La lectura debe ser dinámica: usa `rg --files` para no depender de una enumeración que
quede vieja. Excluye `.git`, caches, entornos y artefactos generados.

## Etapa A — FNC-QA-004: catálogo ejecutable

### Problema que debe resolver

La auditoría encontró tres conjuntos distintos:

1. IDs requeridos por contratos ejecutables;
2. IDs documentados en `TEST_CATALOG.md`;
3. IDs materializados por tests/manifests.

En la base auditada había IDs contractuales ausentes del catálogo y también IDs del
catálogo todavía no presentes en contratos. No los mezcles: el primer caso es drift de
trazabilidad; el segundo puede ser una especificación runtime planeada legítima.

### Modelo autoritativo

`test-catalog-model.json` define política, fuentes y clasificación; no copia manualmente
todos los IDs descubiertos. Debe incluir al menos:

- versión de esquema, task, status, data ceiling y aceptación humana;
- sintaxis canónica y namespaces permitidos para IDs;
- catálogo de clases de fuente y precedencia;
- clasificación de estados: `contract_required`, `catalog_planned`, `implemented`,
  `evidenced`, `waived_pending_human`, `orphan`, `conflict`;
- reglas para distinguir definición de simple mención;
- reglas de provenance: ruta, localizador estable, digest y extractor/version;
- reconciliación contract ↔ catalog ↔ implementation ↔ evidence;
- severidad y owner por tipo de hallazgo;
- política de IDs agregados/rangos sin expandir falsamente cobertura;
- allowlist de archivos y exclusiones deterministas;
- contrato de proyección/diff para el Integration Steward;
- gates, decisiones pendientes y anti-promesas.

### Descubrimiento

Implementa extractores pequeños y explícitos. No busques `TST-` con una sola regex global
y lo llames definición. Distingue como mínimo:

- `required_tests`, `required_test_ids` y equivalentes semánticos en JSON;
- tablas/filas autoritativas del catálogo Markdown;
- nombres, decorators o tablas parametrizadas que materialicen test IDs;
- manifests y registros golden;
- referencias narrativas, que cuentan como mención pero no como implementación.

Cada hallazgo debe conservar todas las procedencias. Una misma ID compatible en varias
fuentes no es duplicado; definiciones incompatibles sí lo son.

### Salidas y CLI

Implementa:

```text
python -m tools.test_catalog.cli discover
python -m tools.test_catalog.cli validate
python -m tools.test_catalog.cli report
python -m tools.test_catalog.cli project --format json
```

- `discover`: inventario estable y ordenado.
- `validate`: exit no-cero ante drift/error según política.
- `report`: conteos por clase, estado, riesgo, owner y gate; no oculta gaps en promedio.
- `project`: propuesta machine-readable de adiciones/correcciones; jamás escribe el catálogo.

JSON por stdout, errores por stderr, salida ordenada y determinista. Agrega `--root` solo
si se valida que queda dentro del repo/copia temporal; rechaza path traversal y symlinks
externos. El código debe aceptar modelo/root inyectables desde tests.

### Invariantes negativas mínimas

1. ID requerido por contrato ausente del catálogo.
2. ID contractual sin owner/gate/riesgo resoluble.
3. ID de catálogo planeado tratado falsamente como implementado.
4. Test implementado sin ID cuando la capa exige trazabilidad.
5. Dos definiciones incompatibles de la misma ID.
6. ID mal formado o namespace desconocido.
7. Rango narrativo contado como múltiples tests implementados.
8. Simple comentario/mención contado como definición.
9. Archivo excluido/caché/vendor contado como fuente.
10. Symlink o ruta externa aceptada.
11. Fuente modificada sin cambio de digest/provenance.
12. Orden de filesystem que cambia el output.
13. Catálogo vacío que pasa por ausencia de descubrimiento.
14. Extractor que ignora dinámicamente un contrato nuevo elegible.
15. Evidencia que no identifica comando, versión, digest y resultado.
16. Waiver sin owner/reviewer/motivo/expiración/gate.
17. Decisión humana marcada aceptada por el agente.
18. Proyección que modifica `TEST_CATALOG.md`.
19. Conteo global que oculta gap crítico.
20. ID retirado sin tombstone/superseded_by cuando la política lo exige.

Incluye pruebas metamórficas: reordenar claves/archivos no cambia el inventario; añadir una
nueva definición contractual elegible sí cambia la reconciliación y debe detectarse.

## Etapa B — FNC-QA-005: mutation harness

### Propósito y límites

El harness demuestra que controles ejecutables reaccionan ante cambios peligrosos. No
pretende verificar infraestructura real, sustituir integration tests, aceptar expected
outputs ni declarar seguridad/contabilidad correctas por un mutation score alto.

Solo puede mutar copias temporales de inputs declarados. No parchea código productivo ni
contratos en el árbol compartido. Empieza con un conjunto pequeño pero representativo de
validadores puros que ya acepten root/model/input inyectable.

### Registro

`mutation-harness.json` debe declarar:

- versión, task, status, límites y aceptación humana;
- módulos/validadores allowlisted con runtime exacto;
- mutation ID, risk/control/test IDs y owner/reviewer;
- target relativo, SHA-256 base y precondición estructurada;
- operador declarativo y parámetros exactos;
- resultado esperado: validator, códigos de hallazgo y exit;
- timeout/output limit/environment policy;
- independencia o grupo de equivalencia de controles;
- clasificación synthetic-only y evidencia;
- estado activo; ninguna mutación skipped cuenta como killed;
- gaps no ejecutables y gate que conservan bloqueado.

Operadores iniciales seguros sugeridos:

- borrar clave/elemento exacto;
- reemplazar scalar exacto;
- insertar elemento/duplicado;
- reordenar estructura sin cambio semántico (control metamórfico);
- sustituir path relativo válido por traversal interno normalizable;
- cambiar bandera de autoridad/seguridad/SoD;
- degradar versión exacta a token flotante.

No implementes eval, snippets Python, regex de reemplazo libre, shell ni comandos recibidos
del registro.

### Ejecución aislada

1. Verifica registro, hashes y precondiciones antes de ejecutar.
2. Crea directorio temporal y copia únicamente inputs allowlisted.
3. Aplica exactamente una mutación por caso salvo grupo explícito.
4. Ejecuta el validador con argv, `shell=False`, cwd validado y entorno mínimo.
5. Limita timeout/stdout/stderr y trata truncamiento como fallo de evaluación.
6. Clasifica `killed`, `survived`, `invalid`, `equivalent_pending_review` o `error`.
7. Verifica al final que los hashes del árbol fuente siguen intactos.
8. Survivor de riesgo crítico produce exit no-cero.
9. `equivalent_pending_review` nunca cuenta como killed automáticamente.
10. El manifiesto de resultado no contiene payloads completos, secretos ni entorno.

### CLI

```text
python -m tools.mutation_harness.cli list
python -m tools.mutation_harness.cli verify
python -m tools.mutation_harness.cli run
python -m tools.mutation_harness.cli run --mutation MUTATION_ID
python -m tools.mutation_harness.cli report
```

`report` muestra por riesgo/control: total, killed, survivors, invalid/equivalent y gaps. No
calcula una única nota aprobatoria. Duraciones pueden mostrarse, pero no entran al digest
determinista.

### Mutaciones iniciales

Incluye al menos 18 mutaciones útiles repartidas entre 6 o más contratos/validadores ya
inyectables. Deben cubrir de forma representativa:

- aislamiento/company scope o frontera de autorización;
- dinero Decimal/float y dirección;
- completitud/Unknown/cierre;
- dedupe/idempotencia sin composite UNIQUE peligroso;
- linaje/engine release/versiones flotantes;
- egress/datos prohibidos/AI fail-closed;
- retry ownership o DLQ sin raw;
- SoD o aceptación humana;
- traversal interno y alteración de input/digest.

No inventes cobertura para TM-002, TM-005, TM-006 o TM-010 si requieren infraestructura o
una superficie aún deshabilitada. Regístralos como gap con owner y gate, coherente con
`test-strategy.json`.

### Invariantes negativas mínimas

1. Registro/hash/precondición alterados.
2. Target absoluto, traversal o symlink externo.
3. Operador, módulo o validator no allowlisted.
4. Comando string/shell/eval/snippet arbitrario.
5. Mutación que toca el árbol fuente.
6. Dos mutaciones accidentales en un caso single-change.
7. Validator no ejecutado que se cuenta como killed.
8. Survivor crítico con exit cero.
9. Excepción/timeout/truncamiento contado como killed.
10. Expected finding distinto aceptado por exit no-cero genérico.
11. Regla redundante contada como control independiente.
12. Equivalent marcado automáticamente sin revisión.
13. Skip/quarantine contado como cobertura.
14. Umbral global inventado como gate aprobado.
15. Runtime/version flotante.
16. Red/proxy/secreto heredado.
17. Manifest con payload raw o entorno completo.
18. Replay idéntico con digest distinto.
19. Mutation ID duplicada o sin risk/control/owner/reviewer.
20. Fixture no sintético o no inventariado.

## Pruebas y calidad conjunta

- Al menos 70 pruebas útiles nuevas combinadas entre QA-004 y QA-005.
- Cada invariante crítica debe tener prueba negativa que muta una entrada válida.
- Añade pruebas de determinismo, independencia del orden, replay y fuente inmutable.
- No dupliques listas de IDs/validadores en modelo, código y tests sin una razón verificada.
- Ningún test puede depender de red, hora real, locale host, orden de directorio o Git.
- Cero `TODO`/`FIXME` anónimo, secretos, emails, NIT, IP pública o dato real.
- Documenta límites honestos: tests verdes prueban el contrato del harness, no el producto.

## Verificación obligatoria

Ejecuta desde la raíz, en este orden:

```powershell
python -m tools.test_catalog.cli discover
python -m tools.test_catalog.cli validate
python -m tools.test_catalog.cli report
python -m tools.test_catalog.cli project --format json
python -m unittest tools.test_catalog.test_validate -v
python -m tools.mutation_harness.cli list
python -m tools.mutation_harness.cli verify
python -m tools.mutation_harness.cli run
python -m tools.mutation_harness.cli report
python -m unittest tools.mutation_harness.test_harness -v
python -m tools.quality_strategy.validate
python -m tools.golden_harness.cli verify
python -m tools.golden_harness.cli run
python -m unittest tools.quality_strategy.test_validate tools.golden_harness.test_harness -v
```

Si `test_catalog validate` falla por el drift preexistente que precisamente modela, eso
puede ser un resultado esperado, pero debe existir un modo de verificación estructural del
modelo que dé PASS y el handoff debe distinguir claramente `model valid` de `repository
has reconciliation findings`. No rebajes la política para forzar verde.

No ejecutes ni declares exitoso `tools.quality_gate.cli`: tus archivos son nuevos y el
gate opera sobre el índice Git. El Integration Steward lo ejecutará al integrar.

## Handoffs

Crea `FNC-QA-004.md` y `FNC-QA-005.md` con:

- base declarada `6e23c04` y aclaración de que no fue verificada por Git;
- rutas creadas/modificadas y rutas liberadas;
- contratos e invariantes implementadas;
- comandos exactos, resultado, conteo de pruebas y mutaciones;
- tabla de gaps/survivors con risk, owner y gate;
- hallazgos fuera de scope sin editarlos;
- decisiones abiertas, riesgos, rollback y compatibilidad;
- revisores independientes requeridos;
- pasos exactos para Integration Steward: indexar, quality gate, CI, catálogo/proyección,
  CURRENT_PHASE, backlog, trazabilidad y release de reservas.

Termina con una sección conjunta de compatibilidad QA-002→003→004→005. No declares head
SHA, integración, CI remoto ni revisión humana inexistentes.

---
task: FNC-QA-002
status: REVIEW_PENDING
base_sha: c227f1c
base_sha_verified: false
integration_sha: see_git_commit_containing_this_handoff
implementer: Claude (external principal dev)
data_used: synthetic_only
human_acceptance: pending
quality_gate_on_git_index: pass_during_integration
---

# Handoff FNC-QA-002 — Estrategia integral de pruebas ejecutable

- **Estado:** `REVIEW_PENDING`
- **Agente:** Claude (external principal dev)
- **Accountable owner:** UNASSIGNED
- **Revisores requeridos:** QA, Architecture, Security, Accounting
- **Base declarada:** `c227f1c`, entregada por el Integration Steward
- **Head SHA:** no disponible — el encargo prohíbe usar Git; no verifiqué la base ni puedo aportar head
- **Rama/worktree:** no aplica; escritura directa sobre el árbol compartido

No declaro gates, ADR, releases, riesgos ni decisiones humanas como aceptados. No se usaron
datos reales, red, credenciales ni conectores.

## 1. Objetivo y resultado

Convertir el seed `TEST_STRATEGY.md` en un contrato que conecte riesgo, control, capa,
caso, evidencia, owner, revisor y gate, sin permitir que un promedio, un skip, un retry o
un mock oculten un defecto financiero.

`test-strategy.json` es la fuente autoritativa; el documento la explica. El validador
comprueba la coherencia y **muerde**: seis mutaciones sobre sus reglas críticas fueron
detectadas por la suite.

## 2. Paths modificados

| Ruta | Estado | Bytes |
|---|---|---:|
| `docs/testing/TEST_STRATEGY.md` | ampliado sobre el seed, no sustituido | 9.108 |
| `docs/testing/test-strategy.json` | nuevo, autoritativo | 29.136 |
| `tools/quality_strategy/__init__.py` | nuevo | 60 |
| `tools/quality_strategy/validate.py` | nuevo | 26.280 |
| `tools/quality_strategy/test_validate.py` | nuevo | 22.737 |
| `docs/implementation/handoffs/FNC-QA-002.md` | nuevo, este documento | — |

**Paths reservados que se liberan:** los cuatro de la ficha.

No toqué `.github/workflows/ci.yml`, `CURRENT_PHASE.md`, `TEST_CATALOG.md`, backlog,
trazabilidad, ADR, contratos de dominio, arquitectura o privacidad, ni ninguna herramienta
existente. Varias de esas rutas cambiaron durante mi ejecución: **es el Integration Steward
trabajando en paralelo**, tal como anunciaba el encargo.

## 3. Conteos del contrato

| Bloque | Cantidad |
|---|---:|
| Capas, cada una con qué prueba y qué **no** prueba | 8 |
| Tipos de oráculo | 5, todos `money_safe` |
| Filas de la matriz riesgo → control → prueba → evidencia | 15 (los quince riesgos de `threat-model.json`) |
| Huecos declarados con owner, gate y motivo | 4 |
| Fuentes de descubrimiento dinámico de IDs | 7 |
| Universo de IDs descubierto | **92** |
| Lanes de CI con orden y dependencias | 6 |
| Módulos con pirámide y frontera declarada | 7 |
| Dominios de control protegidos frente a skip o quarantine | 7 |
| Escenarios de seguridad obligatorios | 8 |
| Códigos de error del validador | 47 únicos |
| Pruebas | **40** |
| Decisiones abiertas | 5 |

### 3.1 Los cuatro huecos declarados

No los disfracé de cobertura. Cada uno bloquea su gate:

| Riesgo | Hueco | Owner | Bloquea |
|---|---|---|---|
| TM-002 | el aislamiento de pool exige PostgreSQL real | Platform | DRG-01 |
| TM-005 | detección de PAN antes de `raw` depende de S-01, sin mecanismo decidido | Security | DRG-00 |
| TM-006 | el escape de worker exige sandbox real | Platform | DRG-01 |
| TM-010 | la IA externa está deshabilitada; no hay superficie ejecutable | AI Platform | L-02 |

## 4. Comandos ejecutados y resultado exacto

```powershell
python -m tools.quality_strategy.validate
python -m unittest tools.quality_strategy.test_validate -v
```

| Comando | Resultado observado |
|---|---|
| `quality_strategy.validate` | `{"discovered_test_ids": 92, "errors": [], "ok": true}`, exit 0 |
| `unittest tools.quality_strategy.test_validate` | `Ran 40 tests` · `OK` |

Los veinte escenarios negativos del encargo están materializados uno a uno como
`test_neg_01` … `test_neg_20`, más doce refuerzos.

### 4.1 Mutación del validador

Cuarenta pruebas en verde no demuestran que las reglas muerdan. Muté seis reglas críticas
en una copia fuera del repositorio:

| Mutante | Regla eliminada | Resultado |
|---|---|---|
| M1 | cobertura de riesgo crítico | **muere** (1 fallo) |
| M2 | rechazo de IDs no descubribles | **muere** (2 fallos) |
| M3 | prohibición de skip en dominio protegido | **muere** (1 fallo) |
| M4 | prohibición de float para dinero | **muere** (1 fallo) |
| M5 | prohibición de dobles en capa de integración | **sobrevivió**, luego corregido |
| M6 | prohibición de umbral inventado | **muere** (1 fallo) |

**M5 sobrevivió y lo dejo documentado porque el motivo importa.** La regla que prohíbe
dobles en `integration`, `security` y `e2e` por nombre de capa es redundante con la que
comprueba la bandera `test_doubles_allowed` de cada capa: mi prueba original activaba las
dos a la vez, así que quitar una no rompía nada. Añadí `test_neg_05b`, que marca la capa
`integration` como si admitiera dobles —la vía de escape sutil— y comprueba que la
prohibición por nombre sigue cerrando la puerta. Con esa prueba, M5 muere.

## 5. Decisiones tomadas dentro del alcance

1. **Los IDs se descubren, no se listan.** `discover_test_ids` los extrae de seis contratos ejecutables más el catálogo. Una lista paralela es drift disfrazado de cobertura y el validador la rechaza.
2. **`coverage_state` con tres valores honestos** en vez de un booleano: `covered_executable`, `covered_contract_only` y `gap_declared`. Hoy nada está en `covered_executable`, porque no existe código productivo que probar; decirlo es más útil que inflar la matriz.
3. **La severidad se toma del threat model**, no se copia. Una divergencia es un error de validación.
4. **Cada capa declara qué no puede probar.** Es la mitad que suele faltar y la que evita que un unit test se presente como prueba de aislamiento.
5. **El presupuesto de rendimiento y las pruebas de accesibilidad con personas quedan `pending_human`.** No inventé umbrales ni afirmé pruebas que no ocurrieron.

## 6. Hallazgos fuera de scope

**`TEST_CATALOG.md` y los contratos ejecutables divergen en ambos sentidos.** Medido con
las siete fuentes declaradas: 79 IDs viven en contratos, 48 en el catálogo, 92 en la unión.

- **44 IDs están en contratos y no en el catálogo** (`TST-BAL-001`, `TST-CLOSE-001`, `TST-CON-002`…`TST-CON-015`, `TST-DLQ-*`, `TST-EXE-*`, `TST-IDEM-002`…`007`, `TST-RET-002`…`005`, `TST-XCON-*`, entre otros). Esto sí es drift: un contrato declara una prueba obligatoria que el catálogo no conoce.
- **13 IDs están en el catálogo y no en contratos** (`TST-RLS-001/002`, `TST-MON-001`, `TST-TEN-001`, `TST-AUTH-002`, `TST-INB-001/002`, `TST-CI-001`, `TST-LOCAL-001`, `TST-META-001`, `TST-DRG-001`, `TST-A11Y-001`, `TST-AI-001`). Estos **no son drift**: son especificaciones de pruebas de runtime que todavía ningún contrato declara. Conviene distinguirlos.

`TEST_CATALOG.md` está fuera de mis rutas y **no lo edité**. Queda registrado como
`UD-QA-CATALOG-DRIFT`, owner QA, revisores Integration Steward y Architecture.

## 7. Riesgos

1. **La estrategia describe intención, no ejecución.** Ninguna fila está en `covered_executable` porque no hay producto que probar. El validador comprueba que el contrato sea coherente, no que el sistema esté probado.
2. **Cuatro riesgos críticos sin cobertura ejecutable.** TM-002, TM-005, TM-006 y TM-010 dependen de infraestructura o de decisiones que no existen. Están declarados y bloquean sus gates, pero siguen siendo huecos reales.
3. **El drift del catálogo crecerá.** Cada contrato nuevo añade IDs; sin un dueño de reconciliación, la brecha se ensancha sola.
4. **La política de mutación no tiene herramienta.** Exijo cinco mutantes por validador y hoy se hacen a mano. Sin tooling en CI, la disciplina depende de que cada agente la repita.
5. **Sin entorno de integración, `lane_integration` y `lane_security` son declaraciones.** `UD-QA-INTEGRATION-ENV`.

## 8. Decisiones abiertas

| ID | Pregunta | Owner | Bloquea |
|---|---|---|---|
| `UD-QA-PERF-BUDGET` | Presupuesto de rendimiento y umbrales por operación | Platform | GA-01 |
| `UD-QA-A11Y-HUMAN` | Alcance y proveedor de pruebas de accesibilidad con personas | Web/UX | GA-01 |
| `UD-QA-CATALOG-DRIFT` | Quién reconcilia el catálogo con los contratos, y cada cuánto | QA | S1-READY |
| `UD-QA-INTEGRATION-ENV` | Entorno de integración para RLS, pool, worker sandbox y restore | Platform | DRG-01 |
| `UD-QA-MUTATION-TOOLING` | Herramienta y presupuesto de mutation testing sostenido en CI | QA | S1-READY |

## 9. Compatibilidad y consumidores

Añade un módulo (`tools/quality_strategy`) y un contrato (`docs/testing/test-strategy.json`).
No cambia esquemas, eventos, contratos compartidos ni herramientas existentes. Los once
validadores hermanos y `synthetic_corpus verify` se ejecutaron después del cambio y siguen
en verde. Sin migraciones, eventos ni feature flags.

El golden harness de FNC-QA-003 consume este contrato: `GH-VALIDATE-STRATEGY` ejecuta este
validador como caso adjudicado.

## 10. Rollback

Eliminar `docs/testing/test-strategy.json`, `tools/quality_strategy/` y este handoff, y
restaurar `docs/testing/TEST_STRATEGY.md` a su versión seed. Nada más que revertir.

## 11. Instrucciones para el Integration Steward

1. Indexar las cinco rutas de §2 más este handoff.
2. Ejecutar `python -m tools.quality_gate.cli` sobre el índice. **No lo ejecuté ni lo declaro exitoso**: opera sobre el índice de Git y mis archivos son nuevos y no indexados.
3. Añadir a CI, en `lane_contract`: `python -m tools.quality_strategy.validate` y `python -m unittest tools.quality_strategy.test_validate`.
4. Completar `integration_sha` en este handoff y en `docs/implementation/tasks/FNC-QA-002.md`, que no modifico.
5. Actualizar `CURRENT_PHASE.md`, backlog y trazabilidad: `FNC-QA-002` a *Review pending*, rutas `docs/testing/TEST_STRATEGY.md`, `docs/testing/test-strategy.json`, `tools/quality_strategy`, handoff. En `TRACEABILITY.md`, `REQ-FNC-054-QUALITY` pasa de *Draft* a *Review*.
6. Decidir sobre `UD-QA-CATALOG-DRIFT` (§6): reconciliar los 44 IDs contractuales ausentes del catálogo y marcar los 13 IDs de runtime como planeados, no como drift.
7. **No marcar** ningún gate como superado ni cerrar ninguna decisión abierta. El validador lo rechazará.

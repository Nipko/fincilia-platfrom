# Handoff — FNC-DOM-006: especificación ejecutable de completitud y saldos

| Campo | Valor |
|---|---|
| Tarea | FNC-DOM-006 |
| Estado | **`REVIEW_PENDING`** |
| Base | `81f7dd9` (`main`), rama `claude/principal-dev` |
| Owner | Accounting |
| Revisores independientes | Architecture, QA |
| Gate | S1-READY — sigue `not_met` |

---

## 1. Qué resuelve

`docs/domain/completeness-balances.json` declara seis pruebas obligatorias que no
tenían implementación. Estaban contadas como deuda desde FNC-DOM-003 y el catálogo las
reportaba como `TCM-CONTRACT-NOT-IMPLEMENTED` indefinidamente.

Ahora las seis ejecutan una invariante real con evidencia reproducible:

| Prueba | Invariante que ejecuta |
|---|---|
| `TST-CMP-001` | precedencia mismatch > unknown > verified; un control requerido sin evaluar es `unknown` |
| `TST-CMP-002` | `not_applicable` exige expectativa versionada con motivo |
| `TST-BAL-001` | fórmula del statement con Decimal exacto; solo cuentan los `confirmed` |
| `TST-BAL-002` | moneda única, misma compañía y mismo statement; un saldo de origen no prueba completitud |
| `TST-EXC-001` | aprobador independiente, expiración, sin auto-match, estado base preservado |
| `TST-CLOSE-001` | las nueve condiciones de cierre, conjuntivas y fail-closed |

## 2. Naturaleza del entregable

Es una **especificación ejecutable**, no la implementación de producto. Vive en
`tools/completeness_engine/` junto a los demás validadores y arneses porque
`docs/platform/workspace-scaffold.json` mantiene `product_code_allowed: false` hasta
que S1-READY sea aprobado por un humano. No se creó nada bajo `apps/`, `packages/` ni
`workers/`.

Cuando llegue la implementación real, este motor es contra lo que debe contrastarse.

## 3. Rutas creadas o modificadas

| Ruta | Cambio |
|---|---|
| `tools/completeness_engine/{__init__,engine,cli}.py` | creadas — motor puro y CLI |
| `tools/completeness_engine/test_engine.py` | creada — 63 pruebas |
| `tests/golden/completeness/statement_balanced.json` | creada — fixture sintético |
| `tests/golden/completeness/period_ready.json` | creada — fixture sintético |
| `docs/domain/COMPLETENESS_ENGINE.md` | creada — documentación |
| `docs/implementation/tasks/FNC-DOM-006.md` | creada — ficha |
| `docs/implementation/BACKLOG_PHASE_0.md` | fila FNC-DOM-006 |
| `.github/workflows/ci.yml` | añade `tools.completeness_engine.test_engine` a la lane de pruebas unitarias |

**No se tocó** `docs/domain/completeness-balances.json`: el contrato es input de casos
golden y de mutaciones con digest adjudicado, y esta tarea no necesitaba cambiarlo. Los
IDs de prueba ya estaban declarados allí; lo que faltaba era la implementación.

## 4. Hallazgo propio durante la implementación

`str(Decimal(0).quantize(...))` produce `0E-12`. Numéricamente correcto, ilegible, y
suficiente para que dos representaciones del mismo importe dejen de compararse byte a
byte. Apareció al contrastar el primer fixture con su expectativa declarada.

Se añadió `format_money()`, que emite siempre punto fijo con doce decimales, y una
prueba que comprueba que la forma canónica **nunca** es notación científica. Habría
mordido en cualquier comparación golden de importes.

## 5. Verificación

| Comando | Exit | Resultado |
|---|---:|---|
| `python -m unittest tools.completeness_engine.test_engine` | 0 | **63 pruebas, OK** |
| `python -m tools.completeness_engine.cli fixtures` | 0 | 2 fixtures, `synthetic_only` |
| `python -m tools.completeness_engine.cli statement …` | 0 | cuadra con su expectativa declarada |
| `python -m tools.completeness_engine.cli close …` | 0 | periodo listo, 0 condiciones sin cumplir |
| `python -m tools.test_catalog.cli report` | 0 | `TCM-CONTRACT-NOT-IMPLEMENTED` **52 → 46**; `implemented` 30 → 36 |
| `python -m tools.quality_gate.cli` | 0 | política de repositorio |
| `python -m tools.work_graph.validate` | 0 | sin huérfanos |
| `python -m tools.golden_harness.cli verify` | 0 | registro golden íntegro |
| `python -m tools.mutation_harness.cli verify` | 0 | registro de mutaciones íntegro |

Pruebas negativas que muerden, entre otras: un `float` como importe, más precisión que
la escala canónica, `NaN`/`Infinity`, un item `proposed` que movería el saldo, un cero
por redondeo etiquetado `balanced`, un item de otra moneda/compañía/statement, importe
negativo, aprobador igual al preparador, excepción sin aprobador independiente,
excepción expirada, excepción que habilita `auto_match`, excepción no divulgada, versión
flotante en el cierre, autorización sin revalidar, y cobertura de matching ofrecida como
completitud.

## 6. Lo que no cambia

- `auto_match_enabled_in_e0` y `product_close_enabled_in_e0` siguen `false`.
- S1-READY sigue `not_met`.
- Ningún gate ni ADR se acepta.
- La política de materialidad se referencia por id; **no** se evalúa. Decidir qué
  diferencia es material es una decisión humana de Accounting.

## 7. Decisiones que corresponden a un humano

| ID | Pregunta | Owner |
|---|---|---|
| `UD-DOM-MATERIALITY` | Qué política de materialidad rige una excepción aceptada y quién la aprueba | Accounting |
| `UD-DOM-TOLERANCE` | Si algún control monetario admite tolerancia y con qué política versionada | Accounting |
| `UD-DOM-ROUNDING` | Qué escala se publica en informes, dado que la interna es de doce decimales | Accounting |

## 8. Rollback

Eliminar `tools/completeness_engine/`, `tests/golden/completeness/`,
`docs/domain/COMPLETENESS_ENGINE.md`, la fila del backlog y la línea de CI. Ningún
contrato ajeno fue modificado, así que el rollback deja el catálogo exactamente como
estaba: las seis pruebas volverían a contarse como no implementadas.

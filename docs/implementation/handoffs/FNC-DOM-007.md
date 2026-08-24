# Handoff — FNC-DOM-007: identidad, idempotencia y dedupe ejecutables

| Campo | Valor |
|---|---|
| Tarea | FNC-DOM-007 |
| Estado | **`REVIEW_PENDING`** |
| Base | `81f7dd9` (`main`), rama `claude/principal-dev` |
| Owner | Architecture |
| Revisores independientes | Security, QA |
| Gate | S1-READY — sigue `not_met` |

---

## 1. Qué resuelve

`docs/domain/idempotency-dedupe.json` declara doce pruebas obligatorias sin
implementación. Nueve son demostrables con lógica pura y quedan materializadas:

| Prueba | Invariante que ejecuta |
|---|---|
| `TST-DED-001` | reentrega exacta de un artefacto devuelve la versión existente |
| `TST-DED-002` | dos transacciones legítimas idénticas sobreviven; nunca hay unicidad dura de negocio |
| `TST-DED-003` | periodos de extracto solapados conservan ambas observaciones |
| `TST-DED-004` | una reversión es una decisión nueva que cita la previa |
| `TST-DED-005` | la similitud entre compañías nunca produce candidato |
| `TST-IDEM-002` | misma clave y mismo payload devuelve lo existente |
| `TST-IDEM-003` | misma clave y otro payload es conflicto y señal de seguridad |
| `TST-IDEM-006` | un id de proveedor solo identifica dentro de su conexión |
| `TST-IDEM-007` | exactamente un dueño del reintento |

## 2. Las tres que **no** se implementan aquí

`TST-IDEM-001` (reclamo concurrente), `TST-IDEM-004` (caída tras commit de dominio) y
`TST-IDEM-005` (worker con lease expirado) exigen PostgreSQL real: inserción atómica,
outbox y token de fencing no se demuestran con funciones puras.

**No se simulan.** Se registra `FNC-DB-004` con ficha, dependencias y rutas reservadas, y
una prueba de esta misma suite (`test_scope_01`) falla si alguien intenta añadirlas aquí
con nombre de test pero sin base de datos.

## 3. La idea que ordena el módulo

Identidad e igualdad no son lo mismo, y confundirlas borra dinero:

- que dos bytes sean idénticos prueba que es **la misma entrega**, no que sea el mismo
  hecho económico;
- que dos movimientos se parezcan muchísimo no prueba que sean el mismo: una empresa
  puede pagar dos veces el mismo importe el mismo día al mismo proveedor, y ambas veces
  son reales;
- por eso fecha, monto, dirección y referencia **nunca** forman unicidad dura. Una
  restricción así no perdería un duplicado: perdería un movimiento real.

## 4. Hallazgo propio: alcance no es identidad

La primera versión ponía `company_id`, `data_source_id` y `connection_id` en el conjunto
de campos de identidad. Con eso, una unicidad dura sobre `(company_id, currency)` pasaba
la validación: tiene un "campo de identidad" y no tiene campos de negocio prohibidos.

Pero `company_id` no identifica nada; **agrupa**. La prueba
`test_TST_DED_002d` lo detectó. Ahora `IDENTITY_FIELDS` contiene solo
`content_sha256`, `provider_event_id`, `artifact_version_id` e `id`, y los alcances
viven en `SCOPE_FIELDS`, que se comprueba por separado.

## 5. Otras decisiones que quedan escritas

- **La huella de candidato es HMAC, no hash.** Un hash de rasgos de negocio es
  reversible por fuerza bruta: el espacio de fechas e importes plausibles es minúsculo.
- **Va versionada tres veces** (clave, locale, regla). Rotar cualquiera cambia la huella;
  si no, un cambio de reglas pasaría inadvertido y el bloqueo dejaría de ser reproducible.
- **Una huella no es una anonimización**: registrarla completa en un log re-identifica los
  rasgos con los que se construyó, y hay prueba de que se rechaza.
- **Un candidato nunca decide.** `automatic_effect` es siempre `none`.
- **Una decisión nunca borra** un movimiento ni su evidencia de origen, y una reversión no
  la puede firmar sola la misma persona que tomó la original.

## 6. Rutas creadas o modificadas

| Ruta | Cambio |
|---|---|
| `tools/dedupe_engine/{__init__,engine}.py` | creadas — motor puro |
| `tools/dedupe_engine/test_engine.py` | creada — 55 pruebas |
| `docs/implementation/tasks/FNC-DOM-007.md` | creada — ficha |
| `docs/implementation/tasks/FNC-DB-004.md` | creada — ficha `proposed` de las tres pendientes |
| `docs/implementation/BACKLOG_PHASE_0.md` | filas FNC-DOM-007 y FNC-DB-004 |
| `.github/workflows/ci.yml` | añade `tools.dedupe_engine.test_engine` |

**No se tocó** `docs/domain/idempotency-dedupe.json`: es input de casos golden y de
mutaciones con digest adjudicado, y los IDs ya estaban declarados allí.

## 7. Verificación

| Comando | Exit | Resultado |
|---|---:|---|
| `python -m unittest tools.dedupe_engine.test_engine` | 0 | **55 pruebas, OK** |
| `python -m tools.test_catalog.cli report` | 0 | `TCM-CONTRACT-NOT-IMPLEMENTED` **46 → 38**; `implemented` 36 → 44 |
| `python -m tools.quality_gate.cli` | 0 | política de repositorio |
| `python -m tools.work_graph.validate` | 0 | sin huérfanos |
| `python -m tools.test_catalog.cli validate` | 0 | sin drift bloqueante |
| `python -m tools.golden_harness.cli verify` | 0 | registro golden íntegro |
| `python -m tools.mutation_harness.cli verify` | 0 | registro de mutaciones íntegro |
| `python -m tools.idempotency_model.validate` | 0 | contrato de origen intacto |

### Por qué bajan 8 y no 9

`TST-DED-002` ya tenía una implementación previa en `tools/lineage_model/test_validate.py`
y por tanto no estaba entre los 46 pendientes. La nueva prueba de esta tarea la cubre
desde el ángulo de la unicidad dura —dos transacciones legítimas idénticas sobreviven— que
es una invariante distinta de la que cubría linaje. Las dos procedencias conviven; el
catálogo las conserva enteras.

## 8. Lo que no cambia

- S1-READY sigue `not_met`; ningún gate ni ADR se acepta.
- El contrato de origen no se modificó.
- La clave HMAC real vive en un vault que no existe en E0: las pruebas usan una clave
  sintética de laboratorio y el motor exige que la clave se pase, nunca la genera.

## 9. Decisión que corresponde a un humano

La rotación de la clave de huella (`candidate_fingerprint_secret`) está declarada como
`vault_managed_rotatable_key` y no hay vault. Quién la custodia, con qué cadencia rota y
qué pasa con los candidatos abiertos durante una rotación es una decisión de **Platform**
con **Security**, y sigue abierta.

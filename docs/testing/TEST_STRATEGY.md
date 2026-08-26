# Estrategia de pruebas v0.1

| Campo | Valor |
|---|---|
| Tarea | FNC-QA-002 |
| Estado | Review pending — amplía el seed v0, no lo sustituye |
| Gate | S1-READY |
| Owners requeridos | QA |
| Revisores | Architecture, Security, Accounting |
| Modelo ejecutable | `docs/testing/test-strategy.json` |
| Validador | `python -m tools.quality_strategy.validate` |
| Datos autorizados | Exclusivamente sintéticos |

`test-strategy.json` es la fuente estructurada **autoritativa**. Si este documento y el
modelo difieren, manda el modelo y la diferencia es un defecto.

El catálogo de IDs sigue viviendo en `TEST_CATALOG.md`. Esta estrategia **no lo edita**:
lo lee como una de sus fuentes de descubrimiento.

---

## 1. Capas

Las ocho del seed se conservan. Lo que añade esta versión es, para cada una, **qué no
puede probar** — que es la parte que en la práctica se olvida.

| Capa | Prueba | **No** prueba | ¿Admite dobles? |
|---|---|---|---|
| Unit | que una transformación respeta su contrato aislado | aislamiento de base de datos, RLS, concurrencia real | sí |
| Property | que una invariante se sostiene sobre un espacio generado | que ese espacio represente el tráfico real | sí |
| Contract | que dos contratos son mutuamente coherentes | que el código productivo implemente el contrato | no |
| Integration | comportamiento real de la frontera con infraestructura | corrección contable ni completitud de una fuente | no |
| Golden | que una salida adjudicada no cambió sin decisión humana | que esa salida sea contablemente correcta | no |
| Security | que un ataque conocido falla cerrado | ausencia de vulnerabilidades no modeladas | no |
| E2E | que las piezas se conectan sobre datos sintéticos | rendimiento, escala ni exactitud financiera | no |
| Usability / a11y | conformidad verificable de criterios automatizables | usabilidad percibida sin prueba con personas | no |

**Un mock no es una prueba de integración.** La política enumera lo que un doble jamás
puede demostrar: enforcement de RLS, aislamiento de contexto en el pool, atomicidad
transaccional, semántica real de replay de un proveedor, versionado y locks del object
store, y reaplicación de tombstones en un restore.

---

## 2. Matriz riesgo → control → prueba → evidencia → gate

Los quince riesgos de `threat-model.json` están en la matriz, con su severidad tomada del
propio modelo: una divergencia de severidad es un error de validación, no una nota.

Cada fila declara un `coverage_state` honesto:

| Estado | Significa |
|---|---|
| `covered_executable` | existe una prueba que se ejecuta y produce evidencia |
| `covered_contract_only` | el control está probado a nivel de contrato, no en runtime |
| `gap_declared` | **no hay cobertura**, con owner, gate y motivo, y bloquea su gate |

Hoy hay **cuatro huecos declarados**, y conviene leerlos como lo que son:

| Riesgo | Hueco | Owner | Bloquea |
|---|---|---|---|
| TM-002 | el aislamiento de pool exige PostgreSQL real | Platform | DRG-01 |
| TM-005 | detección de PAN antes de `raw` depende de S-01, sin mecanismo decidido | Security | DRG-00 |
| TM-006 | el escape de worker exige sandbox real | Platform | DRG-01 |
| TM-010 | la IA externa está deshabilitada; no hay superficie que probar | AI Platform | L-02 |

Un hueco declarado con owner y gate es información. Un hueco disfrazado de cobertura es
un defecto, y el validador lo rechaza.

---

## 3. IDs descubiertos dinámicamente

Los IDs de prueba **no se mantienen en una lista paralela**. `discover_test_ids` los
extrae de siete fuentes: los contratos ejecutables de completitud, idempotencia, linaje,
eventos, vocabulario cruzado y conectores, más `TEST_CATALOG.md`. Hoy el universo
descubrible tiene **92 identificadores**.

Un ID citado por la estrategia que no aparezca en ninguna fuente se rechaza. Un ID
duplicado se rechaza. Una fuente de descubrimiento declarada que no exista se rechaza.

> **Hallazgo reportado, no corregido.** `TEST_CATALOG.md` y los contratos ejecutables
> divergen en ambos sentidos: 30 IDs viven en contratos y no en el catálogo, y 14 viven en
> el catálogo sin respaldo en ningún contrato. `TEST_CATALOG.md` está fuera de las rutas
> de esta tarea. Queda como `UD-QA-CATALOG-DRIFT` para el Integration Steward.

---

## 4. Contrato de caso y de evidencia

Un caso declara: `test_id`, título, capa, tipo de oráculo, owner, revisores, riesgos,
comando, clasificación de datos, determinismo, acceso a red y estado. **No hay skip
silencioso y no hay acceso a red.**

Una evidencia declara: identificador, comando, versión del runtime, digests de entrada,
clasificación, resultado, quién la produjo y quién la revisó. **No transporta payload ni
secretos.** Un test que no registra comando, versión, hash, clasificación y resultado no
es evidencia: es una impresión.

---

## 5. Oráculos

`exact` · `invariant` · `metamorphic` · `property` · `adjudicated_snapshot`

Los cinco son `money_safe`: no existe oráculo aproximado para dinero. El snapshot
adjudicado **no se actualiza automáticamente**; la adjudicación es humana y la persona que
cambia el código no aprueba el expected output que ese cambio modifica.

---

## 6. Flaky, skip, quarantine, retry y waiver

- **Retry prohibido.** Un reintento que convierte rojo en verde oculta un defecto no determinista.
- **Skip prohibido, y nunca silencioso.**
- **Un known failure no es un pass.**
- **Quarantine** exige owner, revisor, motivo, gate de expiración e identificador de seguimiento, y dura como máximo un gate.
- **Waiver** exige `waiver_id`, owner, revisor, motivo, gate de expiración y gate afectado. No se autoaprueba.

Y sobre siete dominios de control **no cabe ni skip ni quarantine**: aislamiento por
company y RLS, dinero y decimal, completitud y saldos, restore y tombstones, seguridad y
egress, linaje y evidencia, idempotencia y dedupe.

---

## 7. Cobertura sin promedios

Un porcentaje agregado no es un gate. La cobertura se enumera **por campo, por empresa y
por formato**, porque un 99,7% agregado es indistinguible de «hay campos publicados sin
linaje» — y es exactamente ese 0,3% el que rompe una auditoría.

Cobertura estructural no es exactitud contable ni calidad de un modelo.

---

## 8. Mutación

Una suite en verde no demuestra que un validador muerda. **Una mutación que sobrevive es
un test que falta**, y así se trata. El mínimo declarado es de cinco mutantes por
validador sobre sus reglas críticas, con evidencia registrada.

---

## 9. Seguridad, contabilidad e IA

**Seguridad.** Ocho escenarios obligatorios —cross-company, pool context, replay,
worker escape, egress no autorizado, resurrección en restore, fuga de telemetría y alcance
de export—, con pruebas negativas, denegación uniforme y sin dobles.

**Contabilidad.** Decimal exacto, moneda explícita, cero float y cero comparación
aproximada. Las seis fechas semánticas permanecen distintas. `unknown` o `partial` bloquean
el cierre. Segregación de funciones obligatoria.

**IA.** JSON válido **no es un oráculo**: prueba forma, no semántica. Se exigen exactitud
semántica por campo, tasa de abstención, calibración, inyección adversarial y recall de
redacción, sobre dataset adjudicado y con monitoreo de drift. Abstención, redacción
fail-closed y fallback son obligatorios. El modelo nunca tiene autoridad financiera.

---

## 10. Rendimiento y accesibilidad

**Rendimiento:** `budget_state: pending_human`, cero umbrales declarados. Medir primero,
fijar después. Un umbral sin presupuesto aprobado es un número inventado.

**Accesibilidad:** WCAG 2.2 AA sobre seis criterios automatizables. La existencia de un
componente **no** es evidencia de accesibilidad, y no se afirma ninguna prueba con
personas que no haya ocurrido: `human_testing_state: pending_human`.

---

## 11. Lanes de CI

| Orden | Lane | Depende de | Gate | ¿Infraestructura? |
|---:|---|---|---|---|
| 1 | `lane_static` | — | S1-READY | no |
| 2 | `lane_contract` | static | S1-READY | no |
| 3 | `lane_unit_property` | static | S1-READY | no |
| 4 | `lane_golden` | contract | S1-READY | no |
| 5 | `lane_integration` | contract, unit/property | DRG-01 | sí |
| 6 | `lane_security` | integration | DRG-01 | sí |

Un lane no puede depender de otro que corra después o a la vez.

---

## 12. Verificación

```bash
python -m tools.quality_strategy.validate
python -m unittest tools.quality_strategy.test_validate -v
```

## 13. Decisiones abiertas

| ID | Pregunta | Owner |
|---|---|---|
| `UD-QA-PERF-BUDGET` | Presupuesto de rendimiento y umbrales por operación | Platform |
| `UD-QA-A11Y-HUMAN` | Alcance y proveedor de pruebas de accesibilidad con personas | Web/UX |
| `UD-QA-CATALOG-DRIFT` | Resuelta por IMP-017: ausencia contractual es drift; runtime planeado es backlog separado | QA |
| `UD-QA-INTEGRATION-ENV` | Entorno de integración para RLS, pool, worker sandbox y restore | Platform |
| `UD-QA-MUTATION-TOOLING` | Resuelta por IMP-017: arnés determinista actual en CI y supervivientes con adjudicación humana | QA |

Ninguna se resuelve aquí. Aprobar este documento no supera S1-READY.

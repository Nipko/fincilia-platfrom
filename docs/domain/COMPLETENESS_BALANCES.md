# Completitud y conciliación de saldos v0.1

| Campo | Valor |
|---|---|
| Tarea | FNC-DOM-003 |
| Estado | Review pending |
| ADR | ADR-014 |
| Owners requeridos | Accounting + Data Engineering |
| Revisores | Product + Security |
| Modelo ejecutable | `docs/domain/completeness-balances.json` |
| Datos | Exclusivamente sintéticos |

## 1. Tres preguntas distintas

1. **Recepción:** ¿llegó un artefacto y pudo procesarse?
2. **Completitud:** ¿la evidencia demuestra el universo esperado para fuente/cuenta/periodo?
3. **Conciliación:** ¿los movimientos y saldos se explican según una ecuación reproducible?

Una respuesta positiva a la primera no implica las otras. Tampoco un alto porcentaje de matches demuestra completitud o saldo conciliado.

## 2. Scope de evaluación

Cada `completeness_assessment` pertenece a una combinación versionada:

```text
company + data_source + source_expectation + period
  [+ financial_account cuando aplica]
  + dataset_version + engine_release
```

La expectativa declara qué controles aplican. No se penaliza una fuente por no ofrecer un control inexistente; ese control queda `not_applicable` con justificación. Si un control necesario debería existir pero no se recibió, queda `unknown` o `mismatch`, nunca se omite.

## 3. Controles

| Control | Compara | Resultado típico |
|---|---|---|
| Conteo | registros esperados vs publicados | match/mismatch/unknown |
| Total débitos/créditos | totales del emisor vs suma exacta | match/mismatch/unknown |
| Saldo apertura/cierre | encabezado/estado vs movimientos | match/mismatch/unknown |
| Continuidad running balance | saldo anterior ± movimientos | match/mismatch/unknown |
| Cobertura de periodo | primera/última fecha y cortes | match/mismatch/unknown |
| Páginas/secciones | total declarado vs recibido | match/mismatch/unknown |
| Secuencia/cursor | huecos, duplicados y finalización | match/mismatch/unknown |
| Procedencia/integridad | firma/hash/canal esperado | match/mismatch/unknown |
| Moneda | fuente, cuenta, totales y registros | match/mismatch |
| Identidad de cuenta | expectativa vs documento | match/mismatch/unknown |

Cada resultado conserva valor esperado/observado tipado, evidencia, tolerancia aprobada, regla/versión y explicación. Las tolerancias monetarias nunca usan float ni ocultan diferencias materiales.

## 4. Derivación del estado

Orden fail-closed:

1. Si un control requerido da `mismatch`, assessment = `mismatch`.
2. Si no hay mismatch pero un control requerido da `unknown`, assessment = `unknown`.
3. Solo si todos los controles requeridos dan `match`, assessment = `verified`.
4. `accepted_exception` no se infiere: es una decisión posterior sobre assessment mismatch/unknown.

`not_applicable` solo vale si la expectativa versionada lo declara y registra razón. No puede usarse como reemplazo de `unknown` después de ver un fallo.

## 5. Elegibilidad

| Estado | Investigar | Sugerir matches | Auto-match | Insumo de cierre | Reporte certificado |
|---|---:|---:|---:|---:|---:|
| `verified` | Sí | Sí | No en E0 | Sí | Sí, sujeto a los demás gates |
| `mismatch` | Sí | No | No | No | No |
| `unknown` | Sí | No | No | No | No |
| `accepted_exception` vigente | Sí | Sí con etiqueta | No | Condicional | Condicional y revela excepción |

Una excepción no cambia el estado base ni prueba completitud. Su alcance puede habilitar revisión/cierre bajo política contable, pero el snapshot conserva la deficiencia y el aprobador.

## 6. Account balance

`account_balance` es una observación versionada de una fuente para una cuenta, moneda, tipo y `as_of`. Opening, closing, running, available y ledger son semánticas distintas. Un available balance no reemplaza closing; un saldo banco no reemplaza libros.

Cada saldo conserva:

- company/account/source/source_record;
- amount decimal exacto y moneda;
- balance type y perspectiva;
- instante/fecha y timezone original;
- lineage, engine release y canonical schema version.

## 7. Reconciliation statement

Por company, financial account, periodo y moneda:

```text
adjusted_bank_balance = bank_closing_balance
                      + confirmed_additions_to_bank
                      - confirmed_deductions_from_bank

unexplained_difference = adjusted_bank_balance - books_closing_balance
```

Solo `reconciling_item` confirmado, vigente, de la misma company/cuenta/periodo/moneda y con evidencia entra en la ecuación. Los propuestos, rechazados o reversados quedan visibles pero no suman.

- `balanced` exige `unexplained_difference == 0` con decimal exacto.
- Una diferencia aceptada crea `accepted_balance_exception`; el statement sigue `exception_accepted`, nunca `balanced`.
- FX exige referencia/version y statement separado o política explícita; no se suman monedas.
- Cerrar un periodo fija saldos, items, assessments, reglas, referencia, schema y engine release.

## 8. Partidas conciliatorias

Una partida declara:

- `item_root_id`, que conserva la identidad de la partida entre decisiones
  append-only, y `statement_root_id`, que la ata a las versiones inmutables del
  mismo statement;
- `add_to_bank` o `deduct_from_bank`;
- importe positivo y moneda;
- razón/tipo;
- evidencia y movimiento/asiento relacionado cuando exista;
- periodo de origen y resolución esperada;
- estado proposed/confirmed/rejected/reversed;
- preparador, aprobador, versión y motivo.

Un preparador no confirma su propia partida cuando la política exige SoD. Reversar crea decisión nueva; no edita la partida usada por un snapshot anterior.
Evaluar nuevas partidas crea una nueva version del statement y conserva la
anterior; la raiz estable evita reasignar o reescribir decisiones historicas.

## 9. Excepciones

Una excepción válida requiere:

- assessment/statement base;
- alcance exacto y monto expuesto cuando aplica;
- razón y evidencia;
- owner;
- aprobador independiente;
- materialidad/política versionada;
- inicio y expiración;
- acciones permitidas;
- audit event.

Expirada, deja de habilitar nuevas decisiones. No elimina cierres históricos que la fijaron; una reapertura crea revisión nueva.

## 10. Close readiness

Un ciclo solo queda `ready_to_close` cuando:

- todas las fuentes esperadas tienen assessment;
- no hay mismatch/unknown sin excepción vigente y admisible;
- cada cuenta/moneda requerida tiene statement;
- cada statement está `balanced` o `exception_accepted` explícito;
- no hay diferencia oculta;
- partidas confirmadas tienen evidencia y SoD;
- campos/decisiones tienen linaje;
- schema, engine y reference data están fijados;
- autorización se revalida antes del snapshot.

Durante E0 no se ejecuta cierre productivo ni auto-match.

## 11. Pruebas obligatorias

- `TST-CMP-001`: required mismatch/unknown nunca produce verified.
- `TST-CMP-002`: control no disponible queda unknown o not_applicable predeclarado.
- `TST-BAL-001`: ecuación decimal exacta y cero.
- `TST-BAL-002`: moneda o account cruzados son rechazados.
- `TST-EXC-001`: excepción sin SoD/expiración no habilita cierre.
- `TST-CLOSE-001`: matches completos no compensan fuente incompleta ni diferencia de saldo.

## 12. Estado

Este contrato queda `Review pending`. Accounting debe aprobar fórmula, balance types, materialidad y excepciones; Data valida controles por fuente; Product valida lenguaje y gates; Security revisa SoD/autorización. No supera S1-READY ni autoriza datos reales.

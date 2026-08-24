# Especificación ejecutable de completitud y conciliación de saldos

| Campo | Valor |
|---|---|
| Tarea | FNC-DOM-006 |
| Estado | Review pending |
| Gate | S1-READY — `not_met` |
| Owner | Accounting |
| Revisores independientes | Architecture, QA |
| Contrato de origen | `docs/domain/completeness-balances.json` (FNC-DOM-003) |
| Código | `tools/completeness_engine/**` |
| Fixtures | `tests/golden/completeness/**` — sintéticos |
| CLI | `python -m tools.completeness_engine.cli` |

---

## 1. Qué es, y qué no

Es una **especificación ejecutable**: convierte las reglas de
`completeness-balances.json` en funciones puras para que sus invariantes se puedan
probar antes de Sprint 1.

**No es la implementación de producto.** Vive en `tools/` junto a los demás
validadores y arneses, no en `apps/`, `packages/` ni `workers/`, porque
`workspace-scaffold.json` mantiene `product_code_allowed: false` hasta que S1-READY
sea aprobado por un humano. Cuando llegue la implementación real, este motor es
contra lo que debe contrastarse, no lo que debe copiarse.

Existe porque seis pruebas que el contrato declara obligatorias
—`TST-CMP-001/002`, `TST-BAL-001/002`, `TST-EXC-001`, `TST-CLOSE-001`— estaban
declaradas y sin materializar. Un catálogo que las cuenta como pendientes para
siempre no protege nada.

---

## 2. El dinero se rechaza antes de redondearse

`parse_money` acepta `str`, `int` y `Decimal`. Un `float` **se rechaza**, no se
convierte:

```python
parse_money(1250000.0)   # MoneyError
parse_money("1250000")   # Decimal('1250000.000000000000')
```

Aceptar un float aquí sería aceptar que `0.1 + 0.2 != 0.3` y que un cierre pueda
cuadrar por suerte. También se rechaza más precisión que la escala canónica
(`numeric(38,12)`), y `NaN`/`Infinity`.

### Una cadena canónica, no dos

`str(Decimal(0).quantize(...))` produce `0E-12`: numéricamente correcto e
ilegible, y suficiente para que dos representaciones del mismo importe dejen de
compararse byte a byte. `format_money` emite siempre punto fijo con doce
decimales. Este detalle apareció al comparar el primer fixture con su expectativa
declarada, y habría mordido en cualquier comparación golden.

---

## 3. Derivación del estado de completitud

Precedencia del contrato: **mismatch > unknown > verified**. Dos reglas importan
más de lo que parece:

- **Un control requerido que nunca se evaluó es `unknown`**, no una omisión
  silenciosa. Si la ausencia se leyera como `verified`, bastaría con no ejecutar un
  control para que un periodo incompleto pareciera verificado.
- **`not_applicable` exige una expectativa versionada con motivo.** Declarar algo
  inaplicable sobre la marcha es la forma más barata de hacer desaparecer un control
  incómodo; sin declaración previa, el resultado es `unknown`.

---

## 4. Conciliación de saldos

```
adjusted_bank = bank_closing + confirmed_additions − confirmed_deductions
unexplained   = adjusted_bank − books_closing
```

- Solo cuentan los items en estado **`confirmed`**. Un item `proposed` que sumara
  convertiría una hipótesis en un ajuste contable.
- Un item de **otra compañía, otra moneda u otro statement** nunca entra, y se
  reporta.
- El importe es **positivo**; la dirección la lleva `adjustment_side`.
- Un item confirmado necesita `approved_by`, `approved_at`, `sod_check` y
  `evidence_refs`, y **quien lo preparó no puede aprobarlo**.
- **`balanced` exige cero exacto.** Un cero por redondeo no es cuadre: es una
  diferencia que nadie vio.

Una diferencia sin explicar solo puede cerrarse con una excepción aceptada válida,
y entonces el estado es `exception_accepted` — **la diferencia sigue ahí**. La
excepción la divulga; no la borra.

Un statement que cuadra no dice nada sobre si la fuente estaba completa: son
preguntas distintas y el motor las mantiene separadas.

---

## 5. Excepciones aceptadas

| Regla | Por qué |
|---|---|
| aprobador independiente | el owner de una excepción no puede aprobarla |
| expiración obligatoria y comprobada | una excepción vencida no autoriza un cierre nuevo |
| `auto_match` prohibido | una excepción divulga un problema; no habilita automatismo |
| estado base preservado | la excepción no convierte un `mismatch` en `verified` |
| divulgación en snapshot e informe | una excepción que nadie ve no es una excepción |

La fecha entra como dato (`as_of`); el motor **nunca consulta el reloj**, para que
dos máquinas obtengan el mismo veredicto sobre el mismo periodo.

---

## 6. Compuerta de cierre

Las nueve condiciones del contrato, evaluadas de forma conjuntiva y fail-closed.
Una prueba comprueba que la lista del código y la del contrato son exactamente la
misma, de modo que retirar una condición del contrato rompe la suite.

Dos confusiones que la compuerta rechaza explícitamente:

- **cobertura de matching no es completitud**;
- **un movimiento emparejado no es una conciliación de saldos**.

Si alguien ofrece la primera como prueba de la segunda, el motor lo dice.

---

## 7. CLI

```bash
python -m tools.completeness_engine.cli fixtures
python -m tools.completeness_engine.cli statement tests/golden/completeness/statement_balanced.json
python -m tools.completeness_engine.cli close tests/golden/completeness/period_ready.json
```

Exit `0` si el fixture cumple lo que declara esperar, `1` si no, `2` por uso
inválido. Rutas confinadas: absolutas, `..` y symlinks se rechazan.

---

## 8. Límites honestos

1. Es una especificación, **no** la implementación de producto.
2. Un motor verde no autoriza ningún cierre: `product_close_enabled_in_e0` sigue
   `false` y `auto_match_enabled_in_e0` también.
3. Los fixtures son minúsculos y sintéticos; nada aquí extrapola a volumen real.
4. No hay ingesta, ni parser, ni conector: los datos entran ya normalizados.
5. La política de materialidad se referencia por id, no se evalúa: decidir qué
   diferencia es material es una decisión humana de Accounting.

## 9. Decisiones abiertas

| ID | Pregunta | Owner |
|---|---|---|
| `UD-DOM-MATERIALITY` | Qué política de materialidad rige una excepción aceptada y quién la aprueba | Accounting |
| `UD-DOM-TOLERANCE` | Si algún control monetario admite tolerancia y con qué política versionada | Accounting |
| `UD-DOM-ROUNDING` | Qué escala se publica en informes, dado que la interna es de doce decimales | Accounting |

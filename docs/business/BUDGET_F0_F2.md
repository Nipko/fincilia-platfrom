# Presupuesto F0–F2

Estado: hipótesis de planeación, no presupuesto aprobado. Corte/TRM: 2026-08-21.

El modelo cubre diez meses, 85–105 persona-mes, costos no laborales y 30% de contingencia.
No cuenta ingresos no contratados. Los costos por persona-mes son supuestos de planeación,
no una afirmación salarial ni una cotización.

| Escenario | Capital COP incl. 30% | USD a TRM 3.062,96 | Burn medio/mes COP |
|---|---:|---:|---:|
| Lean | 2.613.000.000 | 853.100 | 261.300.000 |
| Base | 3.796.000.000 | 1.239.300 | 379.600.000 |
| High | 5.772.000.000 | 1.884.100 | 577.200.000 |

La cifra operativa recomendada para discusión es el rango, no el escenario base aislado.
Antes de contratar, Founder/Finance sustituyen costos por rol y cotizaciones reales, registran
caja/capital comprometido y vuelven a ejecutar el modelo. Ninguna fase se libera por agente.

Fuente de TRM: [Superintendencia Financiera](https://www.superfinanciera.gov.co/CargaDriver/).

```powershell
python -m tools.budget_model.validate
python -m unittest tools.budget_model.test_validate -v
```

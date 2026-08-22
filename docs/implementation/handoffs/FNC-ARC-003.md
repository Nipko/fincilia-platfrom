---
task: FNC-ARC-003
status: REVIEW_PENDING
base_sha: 87d78c5
implementer: Integration Steward
data_used: synthetic_only
human_acceptance: pending
---

# Handoff FNC-ARC-003

## Entrega

- Shortlist factual de regiones administradas en Brasil y Chile con fuentes primarias.
- Contrato por trece planos de datos, no una decisión genérica de país.
- Diez gates legales, contractuales, técnicos, económicos y de salida.
- ADR-020 y solicitud A-02 en estado Proposed.
- Validador cruzado con privacy-map y pruebas de mutación fail-closed.

## Verificación

```powershell
python -m tools.region_decision.validate
python -m unittest tools.region_decision.test_validate -v
```

Resultado observado: contrato válido y 13/13 pruebas de mutación pasan. La evidencia de
proveedores es factual y no constituye selección, cotización ni concepto legal.

## Decisiones pendientes

Legal/Privacy clasifican cada actividad y contrato; Platform completa matriz regional y
benchmarks; Security revisa llaves/soporte/DR; Finance obtiene cotizaciones; Architecture y
Legal son los únicos owners que pueden aceptar ADR-020. No se eligió proveedor o región.

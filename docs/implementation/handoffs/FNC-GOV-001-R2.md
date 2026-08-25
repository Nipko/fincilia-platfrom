---
task: FNC-GOV-001
status: REVIEW_PENDING
base_sha: d4dd80c
decision: IMP-017
accountable_owner: FOUNDER-01
data_ceiling: synthetic_only
---

# Handoff FNC-GOV-001-R2

## Resultado

Se registró `FOUNDER-01` como alias humano estable y accountable provisional de siete
áreas. También se materializó la aprobación humana de las diez decisiones recomendadas
y de ADR-001..010, ADR-023 y ADR-024.

## Separación de funciones

`FOUNDER-01` no cuenta como revisor independiente. Accounting, Database, Security y
Privacy/Legal siguen requiriendo personas distintas. ADR-026 y ADR-027 no se aceptaron.

## Límites conservados

El techo continúa `synthetic_only`; S1-READY, DRG-00 y DRG-01 no se superan por esta
decisión. No se habilitan producción, piloto, datos financieros reales ni proveedores.

## Verificación

```text
python -m tools.founder_governance.validate
python -m unittest tools.founder_governance.test_validate
python -m tools.work_graph.validate
python -m tools.s1_readiness.validate
```

Resultado integrado: 302 pruebas dirigidas verdes; 14/14 golden cases verdes;
68/68 mutaciones muertas; quality gate sin hallazgos sobre el índice. La evaluación S1
es válida y conserva `not_met`, ahora con dos blockers: cadena de suministro y revisión
humana independiente.

`python -m unittest discover` desde el Python global de Windows no es una señal válida
en este workspace: ese intérprete no contiene `psycopg` y falla durante imports de las
suites PostgreSQL antes de ejecutar pruebas. Las suites afectadas se ejecutan en el
contenedor `migrate` según CI; este cambio no modifica API, base de datos ni runtime.

## Siguiente integración

Retirar las diez decisiones de los contratos fuente, actualizar el paquete ADR y
recalcular S1. Los bloqueos resultantes deben distinguir decisión resuelta, evidencia
técnica pendiente y revisión independiente pendiente.

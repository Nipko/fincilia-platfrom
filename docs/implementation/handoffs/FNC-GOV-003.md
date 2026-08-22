---
task: FNC-GOV-003
status: REVIEW_PENDING
base_sha: c6ba08b
implementer: Integration Steward
data_used: synthetic_only
human_acceptance: pending
---

# Handoff FNC-GOV-003

## Entrega

- Grafo derivado del backlog, no una lista duplicada de tareas.
- Normalización de dependencias simples, rangos y agregados.
- Verificación de ciclos, estados, fichas, handoffs, decisiones y trazabilidad.
- Reservas de rutas disjuntas para Claude y el Integration Steward.
- Cálculo determinista y no mutante de siguientes candidatos.

## Verificación

```powershell
python -m tools.work_graph.validate
python -m unittest tools.work_graph.test_validate -v
```

## Revisión requerida

- Architecture: semántica de dependencias provisionales y subtareas sufijadas.
- Security: fail-closed de gates, reservas y promociones.
- Product: prioridades y criterio de disponibilidad de artefactos.

## Límites

El validador no asigna owners, no acepta decisiones, no cambia estados y no inicia agentes.
`review_pending` habilita consumo provisional del artefacto; no satisface un gate humano.


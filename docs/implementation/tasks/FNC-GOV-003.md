---
task: FNC-GOV-003
title: Grafo ejecutable de trabajo, dependencias y reservas
status: review_pending
implementer: Integration Steward
base_sha: c6ba08b
gate: S1-READY
data_ceiling: synthetic_only
independent_reviewers: [Architecture, Security, Product]
---

# Resultado esperado

Convertir backlog, fichas, handoffs, decisiones, trazabilidad y reservas de rutas en un
grafo validable. El grafo debe detectar IDs duplicados, dependencias inválidas o cíclicas,
colisiones de escritura y promociones sin evidencia o aceptación humana.

## Rutas

- `docs/implementation/WORK_GRAPH.md`
- `docs/implementation/work-graph.json`
- `tools/work_graph/**`
- `docs/implementation/tasks/FNC-GOV-003.md`
- `docs/implementation/handoffs/FNC-GOV-003.md`
- Integración central por Integration Steward.

## Criterios de aceptación

1. El backlog se descubre dinámicamente y cada task ID es único.
2. Dependencias abreviadas y rangos se normalizan y deben existir.
3. El grafo dirigido no contiene ciclos, incluidos gates agregados.
4. La ficha coincide con su filename y estados no válidos fallan cerrado.
5. Toda tarea en revisión tiene handoff reproducible.
6. Las reservas activas no se solapan y cubren al implementador externo vigente.
7. `next_candidates` solo propone trabajo sin dependencias bloqueantes; nunca acepta gates.
8. Decisiones y trazabilidad usan referencias conocidas.
9. Las mutaciones negativas prueban que cada control falla.

## Fuera de alcance

- Asignar owners humanos o aceptar gates.
- Crear tareas automáticamente o modificar código de producto.
- Sustituir el backlog Markdown; el JSON contiene política y reservas, no un backlog paralelo.


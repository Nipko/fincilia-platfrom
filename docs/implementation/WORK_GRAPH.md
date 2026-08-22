# Grafo ejecutable de trabajo

Estado: `Review pending` · Tarea: `FNC-GOV-003` · Gate: `S1-READY`.

## Propósito

El backlog Markdown sigue siendo la fuente legible de tareas. `work-graph.json` agrega
únicamente política operativa: estados admitidos, dependencias agregadas, gates humanos y
reservas activas. El validador combina ambos con fichas, handoffs, decisiones y
trazabilidad para evitar que un agente reconstruya el contexto desde conversaciones.

## Reglas

1. Un ID de tarea aparece una sola vez en el backlog y toda dependencia apunta a uno.
2. `DOM-001..005` se expande a cinco dependencias; `Todos` y `Todo F0` se expresan como
   selectores agregados explícitos en el JSON.
3. La ficha de tarea prevalece para el estado operativo, pero no puede inventar un task ID
   ausente del backlog salvo una subtarea sufijada de reconciliación, como `ARC-006A`.
4. `review_pending` significa que existe un artefacto consumible, no que fue aceptado.
5. `done` exige handoff y aceptación humana declarada; los gates nunca los acepta un agente.
6. Dos reservas activas no pueden contener el mismo archivo ni directorios ancestro/descendiente.
7. Una tarea candidata puede empezar solo si sus dependencias están disponibles y no está
   bloqueada, reclamada, en progreso, en revisión o terminada.
8. La salida es una recomendación determinista. No crea tareas, no cambia estados y no firma gates.

## Comandos

```powershell
python -m tools.work_graph.validate
python -m unittest tools.work_graph.test_validate -v
```

La salida incluye conteos, orden topológico y `next_candidates`. Cualquier referencia
desconocida, ciclo, colisión, estado ilegal o ausencia de handoff termina con código distinto de cero.


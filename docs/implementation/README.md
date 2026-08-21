# Paquete de implementación

Este directorio convierte el plan maestro en unidades ejecutables y trazables. Ningún agente necesita reconstruir decisiones desde conversaciones.

## Lectura por rol

Todos:

1. ../../AGENTS.md
2. ../../CURRENT_PHASE.md
3. Su ficha de tarea
4. OWNERSHIP.md
5. ADR y contratos citados

Coordinador:

- WORKSTREAMS.md
- BACKLOG_PHASE_0.md
- TRACEABILITY.md
- GATES.md
- DECISION_LOG.md
- PACKAGE_MANIFEST.md

Implementador:

- DEFINITION_OF_READY.md
- DEFINITION_OF_DONE.md
- templates/TASK.md
- templates/HANDOFF.md

## Estados de tarea

Proposed → Draftable → Ready → Claimed → In progress → Review → Done

Blocked puede aplicarse desde cualquier estado. Done exige evidencia; un mensaje de chat no basta.

## Fuentes de verdad

- El plan define intención, gates e invariantes.
- CURRENT_PHASE define lo permitido ahora.
- Un ADR Accepted define una decisión técnica concreta.
- La ficha define el cambio acotado.
- Las pruebas y el handoff demuestran el resultado.

No se copian fragmentos extensos del plan dentro de tareas. Se citan sección y requisito para evitar versiones divergentes.

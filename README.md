# Fincilia

Plataforma de conciliación y cierre financiero con evidencia para firmas contables y PYMEs.

## Estado

El producto está en preconstrucción. La fase activa permite gobierno del repositorio, investigación, arquitectura, prototipos, entorno local y pruebas con datos completamente sintéticos.

No existe todavía una aplicación productiva. Esta ausencia es deliberada: los contratos, límites de dominio y controles deben superar S1-READY antes de construir código persistente de producto.

## Por dónde empezar

1. Leer [AGENTS.md](AGENTS.md).
2. Leer [CURRENT_PHASE.md](CURRENT_PHASE.md).
3. Abrir el [índice de implementación](docs/implementation/README.md).
4. Tomar únicamente una tarea con estado Ready y alcance de escritura asignado.
5. Entregar un handoff reproducible; el chat no es evidencia de implementación.

## Fuentes de verdad

- [Plan maestro autoritativo](docs/PLAN_MAESTRO_UNIFICADO_FINCILIA.md).
- [Fase y restricciones vigentes](CURRENT_PHASE.md).
- [ADRs](docs/adr/README.md).
- [Backlog de Fase 0](docs/implementation/BACKLOG_PHASE_0.md).
- [Matriz de trazabilidad](docs/implementation/TRACEABILITY.md).

Los documentos rc1 y la revisión de Claude son históricos y no deben dirigir implementación.

## Entorno local

Docker Engine y Docker Compose se ejecutan dentro de Ubuntu sobre WSL 2, sin Docker Desktop. El Compose del proyecto se creará en FNC-PLT-002 después de decidir el stack mediante FNC-PLT-001.


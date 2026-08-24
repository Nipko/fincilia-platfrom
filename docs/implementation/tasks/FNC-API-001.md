---
id: FNC-API-001
alias: FNC-P4.1
title: Creacion atomica y segura de mapeos
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 0d9f022
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Backend, Security, Database, QA]
---

# Resultado esperado

La API crea una plantilla de mapeo y su primera version como una sola unidad:
ambas filas se confirman o ninguna permanece. Las referencias ajenas o inexistentes
se rechazan sin revelar su existencia, un nombre duplicado produce un conflicto
estable y los fallos inesperados no se disfrazan de denegaciones de acceso.

Esta es una rebanada local sintetica fuera de gate. No mueve S1-READY, no habilita
datos reales y no modifica la aplicacion movil.

# Definition of Ready

- `FNC-WEB-001` deja este cierre expresamente para una tarea API dedicada.
- La base es `0d9f022` y el worktree esta limpio.
- V0008 ya define las claves foraneas compuestas y `uq_mapping_name`.
- Se usan exclusivamente empresas, usuarios y extractos sinteticos del entorno local.
- No se cambia esquema, permiso, RLS, semantica financiera ni contrato de publicacion.

# Rutas permitidas

- `apps/api/src/fincilia_api/datasets.py`
- `apps/api/src/fincilia_api/routes.py`
- `apps/api/tests/**` si hace falta una prueba pura adicional.
- `db/tests/test_p3_vertical.py`
- `docs/implementation/tasks/FNC-API-001.md`
- `docs/implementation/handoffs/FNC-API-001.md`
- Registro/liberacion de la tarea en archivos centrales, solo Integration Steward.

# Rutas prohibidas

- `db/migrations/**`, seeds, esquema canonico y datos de referencia.
- `apps/web/**`, `apps/mobile/**` y workers.
- Contratos compartidos, ADR, gates, permisos y CI.
- Datos reales, conectores externos, IA y secretos.

# Criterios de aceptacion

- **AC-01.** La fuente se resuelve bajo el contexto server-side de la empresa antes
  de crear el mapeo; una fuente inexistente o ajena devuelve el mismo 403 neutro.
- **AC-02.** Artefacto, fuente, plantilla y version quedan ligados a la misma empresa.
- **AC-03.** Un fallo al insertar la primera version revierte la plantilla creada.
- **AC-04.** El nombre duplicado dentro de una empresa devuelve RFC 7807 con 409 y
  un codigo estable; no crea una version ni altera la plantilla existente.
- **AC-05.** Errores de integridad de referencias se traducen a 403 sin enumeracion;
  otros errores inesperados conservan su naturaleza de error servidor.
- **AC-06.** El evento de auditoria permitido solo existe cuando ambas inserciones
  tuvieron exito.
- **AC-07.** Pruebas puras aplicables y pruebas contra PostgreSQL real pasan.
- **AC-08.** No se modifica ninguna migracion ni se relaja RLS o permisos.

# Casos negativos

- Fuente inexistente, malformada y de otra empresa.
- Artefacto de otra empresa.
- Nombre ya usado en la misma empresa.
- Error de clave foranea en la segunda insercion despues de crear la plantilla.
- Error inesperado distinto de conflicto o referencia invalida.

# Verificacion

```bash
python -m unittest discover -s apps/api/tests -v
docker compose -f infra/local/compose.yaml -p fincilia-local \
  --profile migrate run --rm migrate \
  python -m unittest db.tests.test_p3_vertical -v
python -B -m tools.work_graph.validate
python -B -m tools.quality_gate.cli
```

# Definition of Done

- AC-01..AC-08 tienen evidencia reproducible.
- El test de rollback consulta PostgreSQL despues del fallo y demuestra cero huerfanos.
- El handoff contiene base/head, comandos, resultados, riesgos y rollback.
- Backend, Security, Database y QA quedan como revisores independientes pendientes.
- Estado final `review_pending`; ningun gate o decision humana cambia de estado.

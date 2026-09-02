---
id: FNC-MAP-001
title: Integridad de fuente entre evidencia y plantilla de mapeo
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 1ce4e4c87e456d2c178d7b0d94c2ec3c36e8301e
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Data, Database, Security, Backend/Architecture, QA]
---

# Resultado esperado

Una plantilla y cada una de sus versiones solo pueden apuntar a evidencia
recibida por la misma fuente inmutable. La regla se aplica en PostgreSQL y no
depende de que la API recuerde comparar dos identificadores.

# Autoridad

- FNC-ING-003 fija `source_artifact.data_source_id` al recibir y prohíbe
  inferirlo para evidencia legacy.
- FNC-API-001 exige creación atómica y rechazo neutral de referencias no
  disponibles.
- ADR-003 conserva `company` como frontera; ADR-004 mantiene evidencia
  inmutable y ADR-015 distingue recepciones legítimas de fuentes distintas.

# Rutas reservadas

- `db/migrations/V0053__mapping_artifact_source_guard.sql` y su ampliacion
  forward-only `V0054__mapping_artifact_source_update_guard.sql`.
- `apps/api/src/fincilia_api/datasets.py`.
- `db/tests/test_p3_vertical.py` y
  `db/tests/test_reconciliation_candidates.py`.
- Esta ficha, un handoff nuevo y registros centrales por Integration Steward.

# Criterios de aceptación

1. PostgreSQL rechaza una versión de mapeo cuyo artefacto pertenece a una
   fuente distinta de la plantilla, incluso evitando la API.
2. Evidencia legacy con fuente nula no se atribuye por mapeo nuevo ni por
   reutilización de plantilla.
3. Crear una plantilla incompatible revierte plantilla y versión de forma
   atómica y devuelve una negativa neutral, sin enumerar la fuente real.
4. Reutilizar una plantilla sobre otra fuente falla antes de producir una nueva
   versión o un evento de auditoría permitido.
5. La fixture de conciliación carga cada documento por la fuente que declara;
   no depende de una combinación inválida que el producto deba rechazar.
6. Migración limpia y replay, pruebas PostgreSQL focales y completas, API,
   quality gate y CI quedan verdes.

# Límites

Solo datos sintéticos. No cambia mapeo financiero, inferencia, publicación,
RLS, SoD, auto-match, cierre ni gates. V0053 es forward-only; no se modifica una
migración ya aplicada.

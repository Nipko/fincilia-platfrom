---
id: FNC-MAP-002
title: Inmutabilidad y transiciones cerradas de versiones de mapeo
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 6ff14cc
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Data, Database, Security, Backend/Architecture, QA]
---

# Resultado esperado

El permiso tecnico `UPDATE` necesario para validar una version no permite
reescribir sus decisiones ni inventar transiciones. PostgreSQL conserva la
version como evidencia reproducible aunque un consumidor evite la API.

# Autoridad

- ADR-004 conserva evidencia y transformaciones reproducibles.
- FNC-P3 define `draft -> validated -> superseded` para la version de mapeo.
- FNC-API-001 crea una version nueva cuando cambia el cuerpo del mapeo.
- FNC-MAP-001 liga de forma inmutable la version a la fuente de su artefacto.

# Rutas reservadas

- `db/migrations/V0055__mapping_version_immutability.sql`.
- `db/tests/test_reconciliation_candidates.py`.
- Esta ficha, un handoff nuevo y registros centrales por Integration Steward.

# Criterios de aceptacion

1. Identidad, empresa, plantilla, numero, artefacto, definicion, digests, autor
   y fecha de una version no se modifican despues de insertarla.
2. Solo se permiten `draft -> validated` con actor/fecha, y
   `validated -> superseded` conservando esos metadatos.
3. Retrocesos, saltos, cambios de validador y mutaciones de una version
   superseded fallan cerrados en PostgreSQL.
4. El endpoint de validacion existente sigue siendo idempotente y compatible.
5. Migracion limpia y replay, pruebas PostgreSQL, quality gate y CI quedan
   verdes con datos exclusivamente sinteticos.

# Limites

No cambia la definicion financiera, la semantica de columnas, RLS, permisos,
SoD, publicacion, auto-match, cierre ni gates. No agrega una ruta de
supersession; solo asegura la maquina de estados ya declarada.

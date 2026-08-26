---
id: FNC-LIN-001
title: Linaje materializado de saldos y decisiones previas al cierre
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: 891a1a0
integration_sha: 830336dac9e63ebe6cc6e51c1a8fa362e21f9232
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Accounting, Data/Architecture, Security, Database, Accessibility/QA]
---

# Resultado esperado

Cerrar la brecha por la que `account_balance`, `completeness_assessment`, sus
controles y `reconciliation_statement` podían declarar linaje sin materializar
la evidencia que lo demuestra. La cadena se conserva digest-only, company-scoped
y reproducible desde la evidencia publicada hasta cada decisión previa al cierre.

La tarea no crea snapshots, no certifica ni ejecuta cierres y no convierte una
revisión humana en aprobación financiera.

# Dependencias y autoridad

- FNC-DOM-005 y ADR-024 fijan el linaje híbrido lógico/físico y cobertura total.
- FNC-CLS-002 aporta observaciones inmutables de saldo.
- FNC-CLS-003 aporta assessments, controles, partidas y statements append-only.
- FNC-CLS-004 consume el estado de linaje sin promoverlo artificialmente.
- Plan unificado §10.1 exige evidencia accesible y linaje completo para cierre;
  esta tarea solo prepara esa evidencia y mantiene el cierre deshabilitado.

# Rutas reservadas

- `db/migrations/V0031__financial_decision_lineage.sql`, `db/migrations/V0032__portable_financial_lineage_triggers.sql`, `db/migrations/V0033__exact_financial_lineage_evidence.sql`, correcciones forward-only
  contiguas de esta rebanada y pruebas DB focales.
- `apps/api/src/fincilia_api/financial_lineage.py`, saldos, conciliación de saldos,
  rutas, esquemas y pruebas focales.
- Contrato de linaje, especificación y validador/pruebas estrictamente necesarios.
- Tipos, cliente, preparación de cierre y pruebas web/E2E/Axe focales.
- Ficha, handoff, backlog, fase, grafo de trabajo y trazabilidad por Steward.

# Criterios de aceptación

- **AC-01.** Un saldo nuevo solo queda `complete` si sus campos `amount` y `as_of`
  tienen nodos digest-only ligados a la fila, plan, ejecución y evidencia exactos.
- **AC-02.** Assessment y controles verificados materializan decisiones y aristas
  hacia el dataset fijado; estado parcial o desconocido nunca se promueve.
- **AC-03.** Partidas y statements conservan la versión de cada insumo y el grafo
  permite descender hasta saldos, assessments y evidencia publicada.
- **AC-04.** Un constraint diferido de PostgreSQL rechaza cualquier INSERT runtime
  que declare `complete` sin el conjunto exacto de nodos y aristas requerido.
- **AC-05.** El endpoint de linaje falla cerrado, aplica RLS y no devuelve valores,
  importes, celdas ni payloads; solo identidad, digests, reglas y coordenadas.
- **AC-06.** La preparación de cierre muestra cobertura y drill-down del statement
  sin botón de cerrar, certificar, aceptar excepción ni modificar hechos.
- **AC-07.** Blank/replay de migración, PostgreSQL cross-company, unitarias API/web,
  E2E, Axe, lint, tipos, build, contratos y quality gate quedan reproducibles.

# Límites y rollback

Solo datos sintéticos. No se reescriben migraciones aplicadas ni filas históricas;
las filas antiguas que no tengan prueba materializada conservan su estado visible.
Rollback de aplicación deja V0031 expand-only y vuelve a presentar el bloqueo.

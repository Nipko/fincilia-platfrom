---
id: FNC-CLS-001
title: Centro diagnostico de preparacion de cierre
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: d81dadd
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Accounting, Security, Backend/Architecture, Product, Accessibility/QA]
---

# Resultado

Dar a contadores una vista company-scoped por periodo que explique qué evidencia
está disponible y qué falta antes de plantear un cierre. La vista nunca declara
`close_ready`, no ejecuta cierres, no certifica saldos y no crea estados
financieros; evidencia de balances y reconciliation statements siguen ausentes
y se muestran como bloqueos explícitos.

# Definition of Ready

- ADR-014 y `completeness-balances.json` definen condiciones fail-closed.
- FNC-OPS-001, DQ-001, RPT-001 y REC-004 aportan ciclos, calidad, informes y
  decisiones humanas sin efecto financiero.
- Base `d81dadd`, árbol limpio y datos exclusivamente sintéticos.

# Rutas reservadas

- `apps/api/src/fincilia_api/close_readiness.py`, `routes.py` y pruebas.
- `db/tests/test_close_readiness.py`.
- `apps/web/src/lib/close-readiness.ts`, `lib/api.ts`, nueva ruta web
  `/preparacion-cierre` y pruebas relacionadas.
- navegación web, ficha, handoff y registros centrales por Integration Steward.

# Criterios de aceptación

- **AC-01.** La API evalúa periodos configurados desde `source_expectation` bajo
  RLS y no acepta `company_id`, conteos ni estados aportados por cliente.
- **AC-02.** Por fuente elige evidencia con regla determinista y visible;
  recepción no implica dataset publicado, completitud o linaje.
- **AC-03.** Pendientes/dispensas, dataset ausente/no publicado, completitud no
  verificada, linaje incompleto, filas rechazadas y fechas contables ausentes se
  presentan como bloqueos cerrados.
- **AC-04.** Revisiones de conciliación abiertas, alertas altas activas y
  correcciones propuestas/aprobadas sin aplicar se cuentan sin leer valores.
- **AC-05.** La ausencia de `account_balance` y `reconciliation_statement`
  productivos mantiene siempre `close_ready: false` y `can_execute_close: false`.
- **AC-06.** No se agregan importes, monedas ni porcentajes de matches; cero
  hallazgos no se presenta como conciliación exitosa.
- **AC-07.** Permiso `report.read`, RLS y consultas company-by-company preservan
  tenancy; empresas fallidas en web aparecen como vista parcial, no como cero.
- **AC-08.** UI accesible permite filtrar empresa/periodo, navegar a fuente,
  calidad y revisiones, y explica cada control sin botón de cierre.
- **AC-09.** Pruebas puras, PostgreSQL/API, web, lint, tipos, build, validadores,
  recorrido visual y handoff pasan; S1-READY no cambia.

# Límites

No añade migraciones, balances, statements, ajustes, excepciones contables,
snapshot, cierre, reapertura, firma, reporte certificado, IA, móvil o datos
reales. Es una proyección diagnóstica descartable mientras falten las entidades
y revisiones humanas del contrato de cierre.

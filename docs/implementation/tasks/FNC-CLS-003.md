---
id: FNC-CLS-003
title: Estados reproducibles de conciliacion de saldos
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 1c58b91
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Accounting, Security, Database/Architecture, Product, Accessibility/QA]
---

# Resultado

Materializar el nucleo de conciliacion de saldos definido por ADR-014: evaluaciones
de completitud, partidas conciliatorias y estados reproducibles por empresa,
cuenta, moneda y periodo. La ecuacion usa dinero decimal exacto y conserva cada
entrada; ningun resultado habilita por si mismo un cierre productivo.

# Definition of Ready

- ADR-014 esta Accepted y `completeness-balances.json` permanece `review_pending`.
- FNC-CLS-002 aporta saldos inmutables respaldados por evidencia, hoy con linaje
  `required_pending` y por tanto inelegibles.
- FNC-REC-004 aporta decisiones humanas append-only sin convertir matches en
  prueba de completitud o de conciliacion de saldos.
- Base `1c58b91`, arbol limpio y datos exclusivamente sinteticos.

# Rutas reservadas

- Contrato canonico, documentacion y validadores de dominio necesarios para
  incorporar las cuatro entidades ya adjudicadas a `reconciliation`.
- Migraciones nuevas desde V0028 y pruebas PostgreSQL focales.
- Modulos y rutas API de assessments, partidas y statements, close-readiness y
  sus pruebas.
- Cliente, acciones, ruta web de conciliacion de saldos, navegacion, estilos,
  Vitest, Playwright y Axe.
- Ficha, handoff, trazabilidad y registros centrales por Integration Steward.

# Criterios de aceptacion

- **AC-01.** `completeness_assessment`, `completeness_control_result`,
  `reconciliation_statement` y `reconciling_item` entran primero al contrato
  canonico con ownership, campos, relaciones, versiones y linaje explicitos.
- **AC-02.** Toda fila productiva lleva `company_id` no nulo y RLS forzada; las
  relaciones compuestas impiden cruzar empresa, cuenta, moneda o periodo.
- **AC-03.** Una evaluacion deriva de expectativa y dataset versionados. La
  ausencia de un control requerido produce `unknown`; nunca se omite ni se
  convierte en `verified`.
- **AC-04.** Una partida usa monto positivo y lado explicito. Solo `confirmed`,
  con evidencia, linaje y separacion preparador/aprobador, entra en la ecuacion.
- **AC-05.** El statement fija saldos banco/libros, assessments, partidas,
  release, esquema y reglas. Calcula con `Decimal` exacto y `balanced` exige
  diferencia exactamente cero.
- **AC-06.** Mismatch, unknown, saldo con linaje pendiente, partida invalida o
  diferencia no explicada dejan el statement en `review_required`.
- **AC-07.** La repeticion exacta es idempotente; una divergencia en la misma
  identidad logica crea conflicto o nueva version, nunca edita el pasado.
- **AC-08.** La API revalida permisos server-side y audita decisiones sin
  registrar importes, referencias o evidencia sensible.
- **AC-09.** La web explica formula, fuentes, estados, partidas contadas/ignoradas
  y diferencia, sin boton ni afirmacion de cierre certificado.
- **AC-10.** Pruebas puras, PostgreSQL/RLS/concurrencia, API, web, E2E,
  accesibilidad, build y validadores pasan con handoff reproducible.

# Limites

No implementa excepciones contables aceptadas, materialidad, snapshot, firma,
cierre/reapertura productivos, reporte certificado, IA, movil ni datos reales.
Mientras los saldos no tengan linaje completo, el statement es diagnostico y
close-readiness permanece bloqueado.

---
id: FNC-CLS-002
title: Observaciones canonicas de saldo por cuenta
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 042a91c
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Accounting, Security, Backend/Architecture, Product, Accessibility/QA]
---

# Resultado

Materializar `account_balance` de punta a punta como observacion financiera
inmutable, company-scoped y respaldada por una fila de evidencia publicada. La
plataforma permite preparar y consultar saldos por cuenta, tipo y fecha sin
presentarlos como prueba de completitud, conciliacion o cierre.

# Definition of Ready

- `account_balance` ya existe en `canonical-model.json` y su semantica esta
  definida por ADR-014 y `completeness-balances.json`.
- FNC-CLS-001 mantiene el cierre siempre bloqueado y separa saldos de estados de
  conciliacion.
- Base `042a91c`, arbol limpio y datos exclusivamente sinteticos.

# Rutas reservadas

- `db/migrations/V0026__canonical_account_balance.sql` y prueba PostgreSQL focal.
- `apps/api/src/fincilia_api/balances.py`, `routes.py`, `main.py` si aplica y
  pruebas relacionadas.
- `apps/web/src/lib/api.ts`, `app/actions.ts`, nueva ruta
  `/empresas/[companyId]/saldos`, navegacion, estilos y pruebas.
- `close_readiness.py` y sus pruebas para diagnosticar presencia y elegibilidad.
- ficha, handoff y registros centrales por Integration Steward.

# Criterios de aceptacion

- **AC-01.** La fila lleva `company_id`, cuenta, registro fuente, tipo, dinero
  decimal exacto, moneda, instante, release, esquema y estado de linaje no nulos.
- **AC-02.** La cuenta y la moneda se resuelven server-side desde una relacion
  activa de la fuente; no se acepta moneda ni empresa aportada por cliente.
- **AC-03.** Solo un dataset publicado, con completitud verificada y linaje
  completo, puede aportar una observacion. La coordenada de celda debe existir.
- **AC-04.** El valor se interpreta con el convenio decimal versionado del
  mapeo; `float`, celda vacia, indice fuera de rango y formato ambiguo fallan.
- **AC-05.** La insercion es inmutable e idempotente por origen/cuenta/tipo/fecha;
  una repeticion identica devuelve la fila y una divergente se rechaza.
- **AC-06.** `close.prepare` escribe; `movement.read` consulta. RLS y claves
  foraneas compuestas impiden mezcla entre empresas.
- **AC-07.** Hasta materializar el camino completo del campo, `lineage_state`
  permanece `required_pending`; ningun saldo asi es elegible para cierre.
- **AC-08.** La web visualiza historico, coordenada, tipo, cuenta, moneda y estado
  de linaje, y permite preparar desde evidencia visible sin afirmar conciliacion.
- **AC-09.** Close-readiness distingue saldos ausentes, observados pero no
  elegibles y elegibles faltantes; `close_ready` y `can_execute_close` siguen falsos.
- **AC-10.** Migracion, API, web, RLS, accesibilidad y regresiones pasan con
  evidencia reproducible y handoff.

# Limites

No implementa `reconciliation_statement`, partidas conciliatorias, excepciones,
snapshot, cierre, reapertura, firma, reporte certificado, IA, movil ni datos
reales. La observacion manual no se marca con linaje completo: completar el
camino desde la celda exige una rebanada separada del plan de transformacion.

---
id: FNC-REC-005
title: Propuestas manuales agrupadas 1:N y N:1 sin efecto financiero
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: a4403d64c270b900c80a0def87e39a90e6d2bba9
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Accounting, Security, Database, Backend/Architecture, Product, Accessibility/QA]
---

# Resultado esperado

Permitir que una persona con `match.propose` componga y conserve un borrador
1:N o N:1 usando un movimiento ancla y entre dos y cuarenta y nueve movimientos
completos del dataset opuesto. La plataforma muestra suma exacta y diferencia
solo como ayuda visual; la propuesta no confirma, distribuye importes, modifica
movimientos, acredita saldos ni habilita cierres.

# Autoridad y decision que habilita

- El PRD requiere lotes, abonos parciales y relaciones 1:N/N:1 como capacidad
  de producto, pero la primera rebanada no modela asignaciones parciales.
- ADR-014/015 y los contratos de completitud/dedupe conservan Decimal exacto,
  evidencia, linaje, historial append-only y decisión humana.
- ADR-027 deja grupos y asignaciones para una decisión posterior. ADR-028
  propone este subconjunto reversible: solo composición manual de movimientos
  completos y sin efecto financiero.
- FNC-REC-001..004 permanecen intactas: el ledger 1:1, sus decisiones y su
  exclusividad no consumen ni son consumidos por estas propuestas agrupadas.

# Rutas reservadas

- `docs/adr/ADR-028-reconciliation-group-proposals.md` y el índice ADR.
- `docs/architecture/adr-readiness.json` y su prueba adjudicada, únicamente para
  registrar ADR-028 como bloqueada sin promoverla.
- `db/migrations/V0035__reconciliation_group_proposals.sql`.
- `db/tests/test_reconciliation_group_proposals.py`.
- `apps/api/src/fincilia_api/reconciliation.py`, `routes.py` y pruebas focales.
- `apps/web/src/lib/api.ts`, acciones y estación web de conciliación.
- pruebas web unitarias, E2E y Axe de conciliación agrupada.
- esta ficha, handoff y registros centrales por Integration Steward.

# Fuera de alcance

- Confirmar o rechazar grupos, N:M, asignaciones parciales, tolerancia o FX.
- Reservar miembros en `match_confirmation_member` o alterar candidatos 1:1.
- Auto-match, score probabilístico, cierre, estados de cuenta o certificación.
- Datos reales, IA, conectores externos, móvil o despliegue compartido.

# Criterios de aceptación

- **AC-01.** Crear exige `match.propose`, empresa resuelta server-side y clave
  idempotente; IDs ajenos o no visibles responden de forma neutral.
- **AC-02.** El servidor canoniza un ancla y 2..49 relacionados distintos, sin
  duplicados ni incluir el ancla, y exige al menos dos datasets.
- **AC-03.** Todos los movimientos pertenecen a la misma empresa y moneda,
  conservan linaje completo y proceden de datasets elegibles validados o
  publicados, con completitud verificada o excepción aceptada.
- **AC-04.** La base impone cardinalidad, orden canónico, pertenencia, moneda,
  elegibilidad y append-only; la API no es la única barrera.
- **AC-05.** La composición es única por empresa, regla, ancla y conjunto. La
  misma clave/payload reproduce y una clave reutilizada conflictúa; carreras
  convergen en un solo borrador.
- **AC-06.** La auditoría permitida y el recibo se confirman atómicamente con el
  borrador. Errores y auditoría no copian importes, referencias ni descripciones.
- **AC-07.** API y web calculan suma/diferencia con decimal exacto, separadas por
  moneda, y declaran `financial_effect=none`, `status=draft` y
  `proves_balance_reconciliation=false`.
- **AC-08.** La interfaz permite invertir el ancla para representar 1:N o N:1,
  exige dos relacionados y nunca ofrece confirmar ni cerrar el grupo.
- **AC-09.** RLS forzada, privilegios mínimos y FK company-scoped impiden fuga,
  reescritura o borrado por runtime; los movimientos quedan inmutables.
- **AC-10.** PostgreSQL real, API, web, E2E, Axe, lint, tipos, build, contratos y
  quality gate pasan; ADR-028 y S1-READY permanecen sin promover.

# Observabilidad, rollout y rollback

Solo se registran IDs, conteo, versión de regla, actor y resultado. El rollout
es local y sintético. El rollback de aplicación retira endpoints/UI y conserva
el ledger append-only; V0035 recibe forward-fix, nunca edición o down migration.

# Handoff

Accounting debe revisar que «diferencia» no implique conciliación ni reparto;
Security/Database revisan RLS, trigger e idempotencia; Architecture revisa el
límite 1:N/N:1; Product y Accessibility/QA revisan lenguaje y operación.

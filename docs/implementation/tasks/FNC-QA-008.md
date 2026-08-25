---
id: FNC-QA-008
title: Regresion web repetible sobre runtime persistente
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: a6de61b
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [QA, Security, Web/UX, Accessibility/Product]
---

# Resultado

Hacer que la regresion web completa sea reproducible sobre el mismo runtime local
persistente que usa el fundador para probar la plataforma. La suite debe respetar
revocacion y ledgers append-only: no borra historia, no reabre decisiones y no
deshabilita versionado de autorizacion para ganar paralelismo artificial.

# Definition of Ready

- FNC-QA-006, FNC-QA-007, FNC-REC-004 y FNC-CLS-003 estan integradas.
- La corrida transversal en `a6de61b` demostro 17/26 en paralelo y 23/26 serial.
- Los fallos paralelos muestran invalidacion legitima de sesiones al versionar
  permisos compartidos; los tres seriales restantes estan acotados a E2E.
- Arbol limpio, stack saludable y datos exclusivamente sinteticos locales.

# Rutas reservadas

- `apps/web/playwright.config.ts`.
- `apps/web/tests/e2e/**`.
- Esta ficha, su nuevo handoff y registros centrales por Integration Steward.

# Rutas prohibidas

- `apps/api/**`, `db/**`, migraciones, seeds y contratos financieros.
- Relajar revocacion, SoD, RLS, auditoria o el ledger append-only.
- Borrar datos persistentes, ejecutar `down --volumes` o fabricar aprobaciones.
- Mobile, IA, datos reales, gates o ADR aceptados.

# Criterios de aceptacion

- **AC-01.** Chromium no ejecuta en paralelo recorridos que comparten usuarios,
  empresa y `authorization_version`; la configuracion explica esta frontera.
- **AC-02.** La navegacion E2E usa el nombre accesible actual y falla si desaparece
  el enlace de cruce de movimientos.
- **AC-03.** Un expediente se localiza por movimientos y pagina exactos, no por
  asumir que permanece en los primeros 25 candidatos.
- **AC-04.** Si existe una revision abierta, el revisor la decide con SoD. Si el
  ledger persistente ya es terminal, la prueba verifica el historico y que no se
  ofrezca volver a decidir; nunca borra ni reabre la fila.
- **AC-05.** Dos corridas consecutivas completas conservan el resultado verde.
- **AC-06.** Las 26 pruebas Chromium y toda la matriz Axe pasan sobre contenedores
  reconstruidos; typecheck, lint, unitarias y build permanecen verdes.
- **AC-07.** El handoff distingue defectos de concurrencia del runner, drift de
  selector y estado terminal legitimo, con rollback y revisores pendientes.

# Limites y rollback

Esta tarea endurece la aceptacion local; no cambia funcionalidad productiva. Un
rollback revierte configuracion y helpers E2E sin tocar la base. La ejecucion puede
crear solamente datos sinteticos mediante las superficies existentes y conserva
todo ledger financiero o de autorizacion.

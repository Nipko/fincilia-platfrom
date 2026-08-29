---
id: FNC-ACC-001
title: Recorrido contable guiado de punta a punta
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: a1f03c7430e30c15ccf0a3ed411c3baf7d4e26bb
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Accounting, Product, Architecture, Accessibility/QA]
---

# Resultado

Cada empresa dispone de un recorrido unico que ordena las capacidades ya
implementadas desde la configuracion hasta el expediente previo al cierre. El
estado de cada etapa se deriva de lecturas autorizadas y conserva diferencias
entre `empty`, `partial`, `unknown`, `verified` y `published`.

# Dependencias

ADR-005, ADR-010, ADR-014, ADR-027 y las rebanadas ING, CLN, REC, CLS, LIN,
EXP, DQ y RPT existentes. Ninguna se reinterpreta ni se promueve.

# Rutas

- `apps/web/src/app/empresas/[companyId]/flujo-contable/**`.
- Componentes y utilidades web necesarias, pruebas Chromium/Axe.
- Enlaces desde portada de empresa y navegacion contextual.
- Ficha, handoff y registros centrales por Integration Steward.

# Criterios de aceptacion

1. El flujo presenta configuracion, ingesta, preparacion, publicacion,
   conciliacion, saldos, revision de cierre e informes en orden comprensible.
2. Cada etapa muestra evidencia real de API o `sin acceso`; nunca traduce una
   denegacion a cero ni una ausencia a completitud.
3. La siguiente accion conserva `company_id` de la empresa autorizada y enlaza
   a la estacion existente adecuada.
4. `partial`, `unknown` y `unverified` permanecen bloqueantes y no se presentan
   como exito.
5. Confirmaciones de match siguen sin efecto financiero y el expediente de
   cierre no ejecuta ni certifica un cierre.
6. El flujo es utilizable a 390 px, por teclado y con lector de pantalla.
7. Unitarias, tipos, build, Chromium y Axe aplicables quedan verdes.

# Fuera de alcance

Cambiar ecuaciones, auto-match, ejecutar cierre/reapertura, certificar informes,
alterar RLS/SoD o procesar datos reales.

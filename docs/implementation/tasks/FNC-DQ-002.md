---
id: FNC-DQ-002
title: Senales avanzadas de riesgo deterministicas y explicables
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: 53f3aa4
implementation_sha: def9c5d
tested_sha: def9c5d
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Product/Accounting, Security, Backend/Architecture, Accessibility/QA]
---

# Resultado esperado

Ampliar el centro de calidad con senales de riesgo combinables, explicables y
reproducibles. Ninguna regla afirma fraude, cambia importes, decide una
conciliacion o alimenta un cierre.

# Rutas reservadas

- `apps/api/src/fincilia_api/quality.py`
- `apps/api/tests/test_quality.py`
- `apps/web/src/app/calidad/**`
- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/web-capabilities.ts`
- `apps/web/src/lib/__tests__/web-capabilities.test.ts`
- `db/migrations/V0058__advanced_quality_risk_signals.sql`
- `db/tests/test_quality_issues.py`
- esta ficha y su handoff
- registros centrales por Integration Steward

# Criterios de aceptacion

1. Las reglas nuevas usan solo datos canonicos company-scoped y Decimal/numeric.
2. Cada senal conserva clave determinista, explicacion tipada y alcance opaco.
3. Un score solo prioriza revision; no prueba fraude ni produce efecto financiero.
4. Una regla individual no eleva por si sola una senal compuesta de alto riesgo.
5. Consultas acotadas, truncamiento visible, RLS y triaje append-only se conservan.
6. La web explica indicadores, limites y accion humana sin exponer valores crudos.
7. Migracion blank/replay, PostgreSQL, unitarias web/API, E2E y Axe quedan verdes.

# Limites

Solo datos sinteticos. No usa IA, listas externas, identidad inferida, biometria,
geolocalizacion ni acusaciones. No acepta DRG-00, DRG-01 o GA-01.

# Evidencia integrada

- Migracion V0058 aplicada y repetida con `mutated: false` sobre PostgreSQL.
- 190 pruebas unitarias API y 3 recorridos verticales PostgreSQL/MinIO: OK.
- 297 pruebas web, lint, TypeScript y build Next: OK.
- 3 recorridos Chromium y 2 recorridos Axe focales: OK.
- Las cinco senales nuevas son deterministas, company-scoped y no exponen
  importes, referencias, descripciones ni huellas.
- La regla compuesta de severidad alta exige al menos dos indicadores avanzados
  distintos sobre el mismo movimiento.

# Revision pendiente

Product/Accounting debe revisar semantica y lenguaje; Security, RLS y ausencia
de valores crudos; Backend/Architecture, limites y plan de consulta; QA y
Accessibility, el recorrido visual. Ninguna revision queda autoaprobada.

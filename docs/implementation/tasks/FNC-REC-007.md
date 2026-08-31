---
id: FNC-REC-007
title: Productividad segura del explorador de conciliación
status: ready
implementer: Codex principal dev + Integration Steward
base_sha: ba91e70
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Accounting, Security, Backend/Architecture, UX/QA]
---

# Resultado

Reducir trabajo manual permitiendo filtrar candidatos deterministas por relación
de referencia y conservar el filtro en URL, paginación y explicación, sin score,
tolerancia monetaria, decisión automática ni efecto financiero.

# Rutas reservadas

- motor, ruta y pruebas de conciliación en `apps/api/**`.
- estación, cliente y pruebas de conciliación en `apps/web/**`.
- pruebas PostgreSQL focales en `db/tests/**`.
- esta ficha, handoff y registros centrales por Integration Steward.

# Criterios de aceptación

1. El contrato admite solo `all`, `matching` y `different`.
2. El filtro se evalúa server-side con empresa resuelta y RLS vigente.
3. Nulos y referencias vacías tienen semántica explícita y determinista.
4. URL, formulario, paginación y API conservan el modo elegido.
5. No cambia importe exacto, moneda, dirección opuesta ni ventana de fecha.
6. No añade score, tolerancia, auto-match, cierre ni certificación.
7. Pruebas positivas, negativas y cross-company pasan con datos sintéticos.

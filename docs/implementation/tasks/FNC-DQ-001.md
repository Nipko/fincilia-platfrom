---
id: FNC-DQ-001
title: Centro de alertas de calidad y anomalias deterministas
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 0ac623c
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Product/Accounting, Security, Backend/Architecture, Accessibility/QA]
---

# Resultado

Detectar inconsistencias reproducibles en datasets y movimientos, presentarlas
por empresa y permitir su triaje humano con auditoria. Las alertas son senales de
calidad: no prueban fraude, no modifican importes, no habilitan publicacion,
auto-match, cierre ni reporte certificado.

# Criterios

1. Reglas cerradas y versionadas usan `numeric` exacto; ningun LLM decide.
2. Cada alerta tiene clave determinista, severidad, alcance opaco y conteo, sin
   copiar importes, descripciones, referencias o valores crudos.
3. RLS y `quality.read`/`quality.manage` se resuelven server-side.
4. Escaneo idempotente y acotado detecta completitud, linaje, rechazos,
   fingerprints repetidos, referencias contradictorias, retrasos y outliers.
5. Tomar, resolver o descartar exige motivo, deja evento append-only y auditoria.
6. La web ofrece resumen, filtros, explicaciones, evidencia navegable y estados
   vacio/restringido/degradado, sin lenguaje de fraude confirmado.
7. Migracion blank/replay, PostgreSQL cross-company, unitarias y E2E pasan.

# Alcance

Rutas reservadas en `work-graph.json`. V0018 es solo local sintetica bajo
`migration-tooling.local_build`; no acepta ADR-002, S1-READY ni ningun data gate.

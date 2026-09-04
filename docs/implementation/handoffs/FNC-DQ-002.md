---
task: FNC-DQ-002
status: REVIEW_PENDING
base_sha: 53f3aa4
reservation_sha: 9d071b5
implementation_sha: def9c5d
tested_sha: def9c5d
data_ceiling: synthetic_only
reviewers_pending: [Product/Accounting, Security, Backend/Architecture, Accessibility/QA]
---

# Handoff FNC-DQ-002 — senales avanzadas de riesgo

## Resultado

El centro de calidad incorpora cinco senales deterministas y explicables sobre
movimientos canonicos: huella duplicada entre datasets, referencia reutilizada,
rafaga de mismo monto y fecha, par de reversion rapida y convergencia de varios
indicadores. La ultima solo eleva a severidad alta cuando coinciden al menos dos
indicadores avanzados distintos sobre el mismo movimiento.

Las senales priorizan revision humana. No afirman fraude, no identifican personas,
no modifican datos financieros y no alimentan auto-match, cierre ni informe
certificado. La API no devuelve importes, referencias, descripciones ni huellas.

## Evidencia ejecutada

- V0058 aplicada y repetida sobre PostgreSQL con `mutated: false`.
- 190 pruebas unitarias API y 3 recorridos PostgreSQL/MinIO: OK.
- 297 pruebas web, ESLint, TypeScript y build Next: OK.
- 3 recorridos Chromium y 2 recorridos Axe focales: OK.
- El conjunto sigue acotado a 100 datasets recientes y 500 hallazgos por regla;
  el truncamiento permanece visible.

## Hallazgo corregido durante la ejecucion

Los fixtures reutilizaban contenido de artefacto constante y una lista amplia
podia quedar ocupada por historial append-only. Cada prueba usa ahora artefactos
unicos y consulta su senal por regla, por lo que no depende del orden ni del
volumen historico.

## Limites y revision

Solo se usaron datos sinteticos. No hay IA, listas externas, geolocalizacion,
biometria ni inferencia de identidad. Product/Accounting revisa semantica;
Security, RLS y minimizacion; Backend/Architecture, consultas y limites; QA y
Accessibility, el flujo visual. Esto no acepta S1-READY, DRG-00, DRG-01 o GA-01.

## Rollback

Revertir primero consumidores web y API. V0058 es forward-only: una base donde
ya se aplico requiere una migracion compensatoria; nunca se modifica su checksum.

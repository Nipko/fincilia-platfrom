---
id: FNC-GAT-006-R4
corrects: FNC-GAT-006
status: REVIEW_PENDING
base_sha: d3f53dc22f4a4b7aa35509e4af66c3641b74696c
integration_sha: pending_this_handoff
data_ceiling: synthetic_only_until_DRG-01
author: Codex principal dev + Integration Steward
independent_reviewers: [Security, Privacy, Database, Data, QA]
---

# Handoff FNC-GAT-006 R4 — evidencia religada tras alertas AWS

## Defecto detectado por CI

FNC-FIN-004 añadió al contrato `aws-private-pilot.json` la medida de costo
bruto y los umbrales de alerta. Ese archivo está sellado por FNC-GAT-006 para
probar que los canales externos permanecen deshabilitados. Aunque no cambió un
canal ni una prueba, su digest dejó obsoleta la evidencia y la suite falló
cerrada en el run `33908432119`.

## Corrección acotada

Se recalcularon únicamente el digest de ese contrato y el digest canónico del
manifiesto. Los 90 casos declarados, selectores, conteo de rutas, controles
`D01-XTENANT`, `D01-INGRESS`, `D01-CHANNELS`, limitaciones y fecha de la
ejecución adjudicada permanecen idénticos.

- contrato AWS: `5f61a8d650112f3e09c7b7c02322654752673a55d83cb7323a98347a458ec5f7`;
- evidencia: `f16a9a1ca90d566c8f9d8a2a8575d91a24277360f5c745d442ea9c2bd1688c25`.

## Límites

Este refresco no convierte alertas de costo en evidencia de aislamiento, no
acepta revisiones humanas y no autoriza datos reales. DRG-00/01 permanecen
`not_met`. Security, Privacy, Database, Data y QA deben revisar de forma
independiente.

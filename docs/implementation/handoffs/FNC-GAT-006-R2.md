---
id: FNC-GAT-006-R2
corrects: FNC-GAT-006
status: REVIEW_PENDING
base_sha: 37d390ca0a47fb634908bd30a384ef6a99642fcc
data_ceiling: synthetic_only_until_DRG-01
author: Codex principal dev + Integration Steward
independent_reviewers: [Security, Privacy, Database, Data, QA]
---

# Handoff FNC-GAT-006-R2 — evidencia ligada al contrato AWS ampliado

## Defecto detectado por CI

El commit de FNC-SUP-003 amplió de forma deliberada
`docs/platform/aws-private-pilot.json` con el proveedor OIDC y el rol ECR. Ese
archivo forma parte de las fuentes selladas por FNC-GAT-006, por lo que la
evidencia anterior quedó obsoleta y los validadores fallaron cerrados en el run
`33357761851`. No falló una invariante financiera ni se autorizó dato real.

## Corrección

El carril `Local platform lifecycle` volvió a ejecutar satisfactoriamente la
suite completa de esquema contra PostgreSQL 17 entre
`2026-08-31T04:40:48Z` y `2026-08-31T04:45:29Z`. Después falló únicamente el
paso que comparaba la evidencia anterior. La evidencia se reemitió con esa hora
de observación y estos digests canónicos:

- fuente AWS: `215eb0eb5bd692a61ea8104ed456e5678f05ee6ab6d1f644393decbe4624e313`;
- manifiesto: `cf77417f95b02e6bf944a212ef984eae7e1142271c17aad988dbcef64484465b`.

Los 90 casos adjudicados, sus selectores, los tres controles técnicos y todas
las limitaciones permanecen idénticos. DRG-00 y DRG-01 continúan `not_met`.

## Verificación requerida en el commit de corrección

- `python -m tools.drg01_technical.cli` debe devolver `ok: true`.
- `python -m tools.drg01_readiness.validate` debe conservar 14 blockers y
  `real_data_authorized: false`.
- CI debe repetir las suites unitarias y PostgreSQL antes de considerar el
  manifiesto vigente.

## Pendiente

Revisión independiente Security/Privacy/Database/Data/QA. Este refresco no
acepta gates, no aplica AWS y no sustituye la evidencia cloud aún pendiente.

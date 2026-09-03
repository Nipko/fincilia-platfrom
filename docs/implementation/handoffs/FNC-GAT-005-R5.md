---
task: FNC-GAT-005
status: REVIEW_PENDING
base_sha: 37df2dbc886862995cfc2359a3a83cccc594ed08
release_candidate_run: 33804614558
data_ceiling: synthetic_only
gate_effect: evidence_only
---

# Handoff FNC-GAT-005 R5 — candidato firmado de rutas canónicas

## Resultado

El candidato manual `33804614558` terminó en verde sobre el `main` exacto
`37df2dbc886862995cfc2359a3a83cccc594ed08`. Incluye los handlers 308 dentro de
`apps/web/src`, por lo que las redirecciones forman parte de los inputs firmados
y no dependen de una configuración Next fuera del alcance del manifiesto.

El workflow construyó y ejercitó API, web y worker, reprodujo el bundle, generó
el SBOM SPDX y firmó procedencia y SBOM con OIDC. El archivo descargado se
verificó fuera del runner contra repositorio, workflow, rama y SHA exactos.

## Evidencia

- Sujeto `fincilia-release.tar.gz`: 224174 bytes, SHA-256
  `002cdb23d93706fa44323651dc7b73da2fad4c689725007116f9011b17a57841`.
- Esquema `V0057`; contrato de bundle `1.1.0`.
- Sigstore de procedencia:
  `a76d87c40efc4a26b13b1a19d484d170af8dfe7c7d8a2e652f3ec1826803bf0d`.
- Sigstore SBOM:
  `55f58544f742d05a934af434fbe99e79202ac826d5503f2b1f95ea38be914261`.
- Los doce inputs del manifiesto se conservan en la evidencia estructurada; el
  input `apps/web/src` cubre 157 ficheros y digest
  `bc7becb48696a414f58fdf521180bb6840c3467622f8d7bec693f09cea3769a4`.
- Las dos attestations pasaron `gh attestation verify` fuera del runner con
  prohibición explícita de runners autohospedados.

## Límites y revisión

La evidencia no autoriza producción ni datos financieros reales. Security y QA
continúan como revisores independientes pendientes; `FOUNDER-01` no cuenta como
segunda mirada. DRG-00 y DRG-01 permanecen sin movimiento.

## Rollback

Un rollback debe apuntar a un artefacto previamente firmado y conservar las
redirecciones de URLs ya publicadas. No reutilizar evidencia de otro SHA como si
cubriera `37df2db`.

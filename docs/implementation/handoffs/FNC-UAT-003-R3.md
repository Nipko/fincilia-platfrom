---
task_id: FNC-UAT-003
status: REVIEW_PENDING
base_sha: 37df2dbc886862995cfc2359a3a83cccc594ed08
release_candidate_run: 33804614558
deployment_command_id: a979e2ec-87cf-4dba-b668-58c8f7305c84
data_ceiling: synthetic_only
gate_effect: evidence_only
---

# Handoff FNC-UAT-003 R3 — borde canónico en inglés

## Resultado observado

AWS UAT ejecuta el artefacto firmado de
`37df2dbc886862995cfc2359a3a83cccc594ed08`. El despliegue SSM terminó `Success`,
verificó los 17 ficheros del bundle y conservó backup, restore-check y rollback.

La sonda read-only del borde pasó 13/13 controles: certificado confiable,
TLS 1.3, HTTP a HTTPS, HSTS y cabeceras de seguridad. Diez rutas públicas,
incluidas las siete legales canónicas en inglés, respondieron 200. Una
comprobación adicional confirmó HTTP 308 y `Location` relativo para cada una de
las cinco rutas históricas en español.

La evidencia estructurada quedó ligada a la revisión desplegada y al digest del
instrumento. No envió cookies, tokens, query strings, cuerpos, identidad ni
información financiera.

## Límites y revisión

La observación demuestra publicación técnica, no aprobación jurídica ni
autorización de datos reales. Security, Platform/SRE y QA permanecen como
revisores independientes pendientes. DRG-00/01 no cambian.

## Rollback

El host conserva `/opt/fincilia-rollback-20260903T205408Z`. Todo rollback debe
usar un artefacto firmado y repetir la sonda del borde antes de declarar el
servicio recuperado.

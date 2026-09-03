---
task_id: FNC-UAT-003
status: REVIEW_PENDING
base_sha: 02c0ffc
implementation_sha: 26e8182f145782815662655d3e51839f1b4c324c
data_ceiling: synthetic_only
gate_effect: evidence_only
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Security, Platform/SRE, QA]
---

# Handoff FNC-UAT-003 — borde HTTPS UAT

## Resultado

La superficie pública de `fincilia.com` pasó una sonda sin autenticación y de
solo lectura. HTTP redirige exactamente al origen HTTPS; TLS valida cadena y
nombre con TLS 1.3; las diez rutas públicas responden 200 y conservan HSTS,
CSP anti-framing sin `unsafe-eval`, `nosniff`, `DENY`, permisos cerrados,
referrer policy y `no-store`.

La sonda envió exclusivamente `HEAD`: cero cookies, autorización, query strings,
cuerpo o contenido descargado. La evidencia no contiene identidad, PII ni dato
financiero.

## Evidencia reproducible

- Instrumento: `tools/uat_edge_probe`, ligado por SHA-256 a la evidencia.
- Implementación observada:
  `26e8182f145782815662655d3e51839f1b4c324c`.
- Observación: `2026-09-03T00:01:49Z`.
- TLS: 1.3, SAN `fincilia.com`, certificado válido hasta
  `2026-11-28T04:27:10Z`.
- Evidencia: `docs/implementation/evidence/FNC-UAT-003.json`, digest canónico
  `e1c610d4d7dc9ddb5f362ba08147c9f56ab72fe3ead4638f96bb07051e66933e`.
- Unitarias: 4, OK; nueve mutaciones críticas más digest y SHA muerden.
- Grafo: 135 tareas, 355 dependencias, sin hallazgos.
- Quality gate sobre índice: sin hallazgos antes del commit de implementación.

## Límites y revisión

No se cambió DNS, certificado, Caddy, AWS, aplicación ni datos. La sonda no es
pentest, escaneo de puertos ni autorización de producción. Security debe revisar
políticas/cifrado; Platform/SRE, terminación y renovación; QA, rutas y mutantes.
Ninguna revisión independiente fue inferida y DRG-00/01 siguen cerrados.

## Rollback

Revertir el commit de evidencia y `26e8182`; no existe rollback operativo porque
la entrega no mutó el edge. Si cambia el código de sonda, el validador rechaza la
evidencia por digest y exige una nueva observación.

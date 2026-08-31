---
task_id: FNC-SEC-006
status: REVIEW_PENDING
base_sha: ba91e70
implementation_sha: b44c115
tested_sha: 2bc936a
data_ceiling: synthetic_only
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Security, Architecture, QA]
---

# Handoff FNC-SEC-006 — endurecimiento HTTP verificable

## Resultado

API y web emiten una baseline defensiva comprobable. La API aplica tambien en
errores controlados `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, una
`Permissions-Policy` cerrada y `Cross-Origin-Resource-Policy: same-origin`.

La web incorpora cabeceras equivalentes, CSP sin `unsafe-eval` y aislamiento
`Cross-Origin-Opener-Policy` compatible con el flujo OAuth por redireccion. No se
emite HSTS desde el runtime HTTP local: su autoridad corresponde al edge HTTPS.

## Evidencia reproducible

- pruebas API verifican valores exactos en respuestas exitosas y errores.
- `public-shell.spec.ts` verifica las cabeceras reales servidas por Next.
- 42 recorridos Chromium y 26 Axe por cada una de dos corridas UAT limpias.
- typecheck, lint, pruebas web y build pasaron en la integracion del bloque.

## Limites, revision y rollback

No se implementan aqui TLS, HSTS del edge, WAF, rate limiting global, rotacion de
secretos ni aceptacion de riesgo. No se registran tokens, payloads, identidad o
informacion financiera. Security debe revisar la CSP y los valores; Architecture
la division de autoridad edge/runtime; QA los casos de error. No existe aun
revision independiente aceptada.

Revertir `b44c115` restaura la baseline anterior sin tocar OAuth, datos o esquema.

## Rutas liberadas

Middleware y pruebas HTTP de API, configuracion y E2E de cabeceras web, ficha,
handoff y registros centrales.

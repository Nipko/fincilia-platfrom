---
task: FNC-LEG-002
status: REVIEW_PENDING
base_sha: ddb0c24
implementation_sha: 37df2dbc886862995cfc2359a3a83cccc594ed08
release_candidate_run: 33804614558
data_ceiling: synthetic_only
gate_effect: evidence_only
---

# Handoff FNC-LEG-002 R4 — publicación AWS de URLs inglesas

## Corrección integrada

R3 describía redirects en `next.config.mjs`, un fichero que no pertenecía a los
inputs firmados del candidato. La implementación final mueve las cinco rutas de
compatibilidad a handlers GET/HEAD dentro de `apps/web/src`, valida que el
destino sea relativo y conserva HTTP 308. Así, una URL externa no puede
introducir un open redirect y la conducta desplegada queda cubierta por el
manifiesto de release.

Las URLs canónicas son `/privacy`, `/terms`, `/cookies`, `/security`, `/dpa`,
`/subprocessors` y `/delete-account`. Las rutas españolas no se deben registrar
en Google; existen únicamente para compatibilidad.

## Verificación

- ESLint y TypeScript: exit 0.
- Vitest: 52 archivos y 292 pruebas, OK.
- Build Next: 19 rutas, OK.
- Playwright público: 6/6, incluidas cinco redirecciones 308 y metadatos
  `rel=canonical`.
- Axe público: 5/5 sin hallazgos serios o críticos.
- Candidato `33804614558` firmado y verificado fuera del runner.
- AWS UAT ejecuta `37df2db`; las siete URLs canónicas responden HTTPS 200 y las
  cinco anteriores responden 308 hacia el destino inglés.

## Límites

No cambia el contenido, la versión legal activa ni los gates. Las revisiones
independientes Legal/Privacy, Security, Product y Accessibility/QA siguen
pendientes. No autoriza registro público ni datos reales.

## Rollback

Revertir con un candidato firmado previo y mantener redirecciones para enlaces
ya distribuidos. Coordinar cualquier cambio con las URLs configuradas en Google.

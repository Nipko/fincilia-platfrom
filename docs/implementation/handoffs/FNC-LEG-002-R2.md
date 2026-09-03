---
task: FNC-LEG-002
status: REVIEW_PENDING
base_sha: e9f0045
implementation_sha: 17254348a0a5b2aef70ad18d0eeb68e1054a50a5
data_ceiling: synthetic_only
gate_effect: evidence_only
---

# Handoff FNC-LEG-002 R2 — publicación legal en inglés

## Resultado

Las siete páginas del centro legal se publican completamente en inglés sin
cambiar las URLs registradas en Google: privacidad, términos, cookies,
seguridad, DPA, subprocesadores y eliminación. Cada página declara `lang=en`,
incluye título y descripción para buscadores y mantiene a Parallext LLC, su
domicilio, teléfono y canales `@fincilia.com` como identidad jurídica visible.

La política explica de forma explícita cómo Fincilia accede, usa, almacena y
comparte los datos mínimos de Google (`openid email profile`) y excluye Gmail,
Drive, contactos, calendarios, publicidad, venta y entrenamiento de IA.

## Versionado y persistencia

V0057 amplía de forma compatible el formato de versión con un sufijo opcional
de idioma y activa `terms-2026-09-03-en` y `privacy-2026-09-03-en`. V0043,
V0056 y todas las aceptaciones existentes permanecen intactas. La API, el flujo
web y PostgreSQL usan exactamente los mismos identificadores.

## Límites

- Esto es una traducción y publicación técnica, no una aprobación jurídica.
- No habilita personas, datos ni operaciones reales: continúa
  `synthetic_only` hasta los gates correspondientes.
- El DPA continúa siendo un modelo no ejecutado.
- Privacy/Legal, Security, Product y Accessibility/QA deben revisar en forma
  nominal e independiente la versión publicada.

## Evidencia reproducible

| Comprobación | Resultado |
| --- | --- |
| `npm run lint` | exit 0 |
| `npm run typecheck` | exit 0 |
| `npm run test:unit` | 51 archivos, 289 pruebas, OK |
| `npm run build` | 14 páginas estáticas, OK |
| Playwright `public-shell.spec.ts` | 5 pruebas, siete rutas legales verificadas, OK |
| suite unitaria API | 188 pruebas, OK |
| V0057 contra PostgreSQL real | aplicada, `head: V0057`, `mutated: true` |
| repetición del migrador | `head: V0057`, `mutated: false` |
| suite de esquema completa | 412 pruebas, OK, 1 omitida |
| escala sintética | 100.000 movimientos en 42,4 s, bajo el límite de 60 s |
| `tools.migration_readiness.validate` | `ok: true`, 57 migraciones |
| `tools.work_graph.validate` | 140 tareas, 371 aristas, `ok: true` |
| `tools.runtime_config.validate` | 53 variables, `ok: true` |
| `tools.web_functional_status.cli` | implementación 88%, `ok: true` |

La comprobación HTTPS de `fincilia.com` se registra después de desplegar el
artefacto firmado; no se presenta la validación local como evidencia pública.

## Rollback

El contenido puede revertirse con código, pero V0057 es forward-only. Para
retirar las versiones inglesas se publica otra migración que active versiones
sucesoras; nunca se borran versiones ni aceptaciones históricas.

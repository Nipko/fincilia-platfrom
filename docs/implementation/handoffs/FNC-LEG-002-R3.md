---
task: FNC-LEG-002
status: REVIEW_PENDING
base_sha: 82e53c2bef5b993d219bf50bca8411f38fbba245
implementation_sha: c2fe857
data_ceiling: synthetic_only
gate_effect: evidence_only
---

# Handoff FNC-LEG-002 R3 — rutas legales canónicas en inglés

## Resultado

El centro legal conserva su contenido público en inglés y adopta rutas
canónicas inglesas: `/privacy`, `/terms`, `/cookies`, `/security`, `/dpa`,
`/subprocessors` y `/delete-account`. Los enlaces de portada, ingreso,
registro, cuenta, footer y navegación entre documentos apuntan únicamente a
esas rutas.

Las cinco rutas anteriores en español permanecen como redirecciones HTTP 308.
Esto evita contenido duplicado, conserva enlaces ya distribuidos y permite
registrar en Google únicamente las URLs canónicas. Cada página canónica expone
además `rel=canonical` con origen `https://fincilia.com`.

## Evidencia reproducible

| Comprobación | Resultado |
| --- | --- |
| ESLint web | exit 0 |
| TypeScript web | exit 0 |
| Vitest web | 51 archivos, 289 pruebas, OK |
| Next production build | 14 páginas generadas, OK |
| Playwright `public-shell.spec.ts` | 6/6, incluidas cinco redirecciones 308 y siete canónicas |
| Axe público | 5/5, sin hallazgos serios o críticos |
| `tools.uat_edge_probe.test_probe` | 4/4, OK |

La evidencia pública HTTPS de FNC-UAT-003 se regenerará después de desplegar
el artefacto firmado. El build local no se presenta como evidencia del borde.

## Límites y revisión

- No cambia el texto ni las versiones legales activas
  `terms-2026-09-03-en` y `privacy-2026-09-03-en`.
- No activa Google, registro público, datos reales ni operaciones reales.
- No mueve DRG-00, DRG-01 ni ningún gate.
- Privacy/Legal, Security, Product y Accessibility/QA siguen requiriendo
  revisión nominal independiente.

## Rollback

Revertir el commit de implementación restaura las rutas anteriores como
canónicas. No toca esquema, aceptaciones, cuentas ni documentos. Si las URLs
ya fueron registradas en Google, el rollback debe coordinar la reversión de
esa configuración para evitar enlaces públicos inconsistentes.

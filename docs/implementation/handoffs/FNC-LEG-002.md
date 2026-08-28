---
task_id: FNC-LEG-002
status: REVIEW_PENDING
base_sha: 60fb0a0af60bda96df742cbc073e8c6a38857243
implementation_sha: 95146e3c9cc1b81357d7d1edffc620a0a2e366db
tested_head_sha: 95146e3c9cc1b81357d7d1edffc620a0a2e366db
data_ceiling: synthetic_only
gate_effect: evidence_only
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Privacy/Legal, Security, Product, Accessibility/QA]
---

# Handoff FNC-LEG-002 — centro legal público

## Resultado

Fincilia dispone de portada pública y un centro de confianza navegable sin
sesión: privacidad, términos de la beta, cookies, seguridad, DPA,
subencargados y eliminación de cuenta. Todos los documentos identifican a
Parallext.com como desarrollador, muestran versión y fecha, y se presentan
explícitamente como borradores pendientes de revisión jurídica.

El alta exige dos confirmaciones independientes, ambas verificadas de nuevo en
el servidor: uso exclusivo de datos completamente sintéticos y aceptación de
los términos con lectura de privacidad. La política delimita el futuro acceso
de Google a `openid email profile`; Google no está activado y DRG-00/01 no
cambian.

## Controles y límites

- La portada no promete contabilidad certificada, disponibilidad ni uso con
  datos reales; destaca el techo sintético antes del primer CTA.
- No se inventó razón social, NIT, domicilio, jurisdicción ni entidad
  contratante. El contacto provisional publicado es `support@parallext.com`.
- Cookies documenta sesión y material OAuth transitorio; no afirma analítica ni
  publicidad activa.
- DPA es una plantilla prevista, no un acuerdo firmado.
- Seguridad separa controles existentes de condiciones todavía pendientes
  para DRG-01.
- El registro falla cerrado si cualquiera de los consentimientos falta, aunque
  un cliente omita la validación HTML.
- No hay proveedor nuevo, telemetría, secreto, PII, documento real, migración,
  cambio de autorización ni activación de Google.

## Evidencia reproducible

| Verificación | Resultado |
|---|---|
| TypeScript | OK |
| ESLint web | OK |
| Vitest web | 35 archivos / 229 pruebas, OK |
| Build Next de producción en Docker | OK; 12 páginas públicas/dinámicas generadas |
| Chromium: shell + alta completa | 6/6, OK |
| Axe: shell, portada, privacidad y flujos existentes | 9/9, sin hallazgos serios o críticos |
| Quality gate sobre índice Git | OK, 0 findings |
| Revisión visual en navegador | portada y privacidad, desktop, OK |

Comandos principales:

```text
npm --prefix apps/web run typecheck
npm --prefix apps/web run lint
npm --prefix apps/web run test:unit
FINCILIA_LOCAL_WEB_PORT=53100 docker compose -f infra/local/compose.yaml up -d --build --wait web
FINCILIA_E2E_BASE_URL=http://127.0.0.1:53100 npm --prefix apps/web run test:e2e -- tests/e2e/public-shell.spec.ts tests/e2e/self-service-registration.spec.ts
FINCILIA_E2E_BASE_URL=http://127.0.0.1:53100 npm --prefix apps/web run test:a11y -- tests/e2e/public-shell.a11y.spec.ts
python3 -m tools.quality_gate.cli
```

## Revisión pendiente y rollback

Privacy/Legal debe adjudicar entidad, jurisdicción, bases, plazos y texto
contractual; Security, exactitud del posture y divulgación; Product, lenguaje
de invitación; Accessibility/QA, navegación y legibilidad. El implementador y
Founder no cuentan como revisión independiente. Hasta esas firmas el resultado
es `REVIEW_PENDING`, aporta evidencia a BETA-01 y no supera ningún gate.

El rollback restaura la redirección de `/`, retira enlaces y páginas públicas y
elimina los dos controles UI/servidor. No requiere revertir datos ni esquema.
Las rutas quedan liberadas con este handoff.

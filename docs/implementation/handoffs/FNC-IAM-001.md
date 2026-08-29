---
id: FNC-IAM-001
status: REVIEW_PENDING
base_sha: 3ec2893
integration_sha: 99c9445
data_ceiling: synthetic_only_until_DRG-00
author: Codex principal dev + Integration Steward
independent_reviewers: [Security, Privacy/Legal, Architecture, QA]
---

# Handoff FNC-IAM-001 — identidad administrada y onboarding Google

## Resultado integrado

La identidad administrada quedó implementada de extremo a extremo sin usarla
como fuente de autorización financiera. Cognito valida la identidad; PostgreSQL
continúa resolviendo `subject_id`, firma, empresa, membresía y roles.

- `3ec2893` integra el intercambio server-side, enlace de identidad por HMAC,
  invitación de un uso, alta atómica y funciones `SECURITY DEFINER` acotadas.
- `99c9445` integra el BFF web, Authorization Code + PKCE S256, state, nonce,
  cookie transitoria AES-256-GCM y pantallas de acceso/registro con Google.
- La API consulta `GetUser` como fuente autoritativa del token de acceso. El
  `refresh_token` que Cognito entrega en Code flow se descarta en memoria y no
  se copia, persiste, registra ni devuelve.
- Los tokens, correo, `sub`, código de invitación y secretos no se incluyen en
  URLs propias, respuestas, auditoría o logs. Correo y `sub` se referencian por
  HMAC con claves versionadas.
- El modo local permanece separado y rotulado como laboratorio sintético.
- `docs/platform/GOOGLE_OAUTH_PUBLICATION.md` fija los datos requeridos, las
  páginas públicas y la matriz Google→Cognito→Fincilia sin almacenar secretos.
- El output no sensible `cognito` expone por separado origen/redirect de Google
  y callback de Fincilia para impedir que se intercambien al configurar.

## Evidencia reproducible

| Comando | Resultado |
| --- | --- |
| `docker build --target build -f apps/web/Dockerfile -t fincilia-web-test .` | build Next.js y TypeScript OK |
| `docker run --rm -e NODE_ENV=test fincilia-web-test npm run lint` | exit 0 |
| `docker run --rm -e NODE_ENV=test fincilia-web-test npm run test:unit` | 38 archivos, 241 pruebas, OK |
| `python3 -m tools.runtime_config.validate` | `ok: true`, 51 variables |
| `python3 -m unittest tools.runtime_config.test_validate` | 11 pruebas, OK |
| `python3 -m tools.quality_gate.cli` sobre el índice | `ok: true`, 0 hallazgos |

La revisión visual cubrió `/entrar` y `/registro` en los modos local y
administrado. Detectó y corrigió antes de integrar una colisión CSS que hacía
invisible el texto de “Crear una cuenta”.

La evidencia PostgreSQL del commit backend incluye cuatro pruebas de identidad
administrada, 19 pruebas de cola y 64 pruebas de migración; las migraciones
V0041/V0042 permanecen inmutables.

## Pendientes externos y revisión

1. Configurar dominio, Cognito User Pool/client, proveedor Google y secretos
   exclusivamente en AWS; no copiar valores al repositorio ni al handoff.
2. Demostrar issuer, audience, callback exacta, MFA, revocación y rotación en el
   entorno `private-pilot`.
3. Obtener revisión independiente nominal de Security, Privacy/Legal,
   Architecture y QA. `FOUNDER-01` no cuenta como revisor independiente.
4. No activar `FINCILIA_OIDC_ENABLED` para información real hasta DRG-00; la
   identidad completa es evidencia necesaria, no autorización suficiente.

## Rollback

Desactivar `FINCILIA_OIDC_ENABLED`, revocar el client de Cognito y volver al
bundle anterior. No se modifica ni borra la identidad interna existente; el
acceso local sintético permanece disponible solo en su entorno aislado.

---
id: FNC-IAM-004
status: REVIEW_PENDING
base_sha: 08762c5318ec7132fac0c9f21ef9b79e066cfb17
implementation_sha: 762cde9c27fb3a5458c16dcc22cf65a8eb4d75ac
integration_sha: pending_integration_commit
data_ceiling: synthetic_only_until_DRG_00
---

# Handoff FNC-IAM-004 — alta pública definitiva con Google

## Resultado entregado

Fincilia tiene un único recorrido administrado de identidad orientado al
producto final, sin infraestructura de invitaciones:

- `login` resuelve una identidad existente y nunca crea filas;
- `register` exige nombre de firma y aceptación separada de términos y
  privacidad;
- PostgreSQL crea sujeto, binding HMAC, firma, membership `owner` y dos
  aceptaciones legales en una sola transacción;
- Google/Cognito autentica, pero no concede empresa, rol ni permiso;
- el registro nativo con password de Cognito continúa cerrado;
- `disabled|public_google` permite cerrar altas nuevas sin romper el login de
  cuentas existentes.

No se habilitaron datos reales, pagos, IA, auto-match, cierre ni autorización
por claims externos.

## Cambios principales

1. `V0043` incorpora una referencia HMAC única de correo verificado, catálogo
   de versiones legales, evidencia de aceptación y la función acotada
   `register_external_account_public`.
2. La API separa payloads `login|register`, rechaza perfiles mezclados y
   registra auditoría de alta y apertura de sesión en la transacción exterior.
3. La web conserva Code+PKCE, state y nonce; fija las versiones legales dentro
   de la transacción OIDC cifrada y redirige el alta a `/empresas/nueva`.
4. IaC prepara Cognito/Google para alta pública federada, mantiene `SignUp`
   nativo cerrado y publica el stage como `preproduction`.
5. IMP-020 registra la decisión del Founder. La decisión de assurance/step-up
   sigue abierta y ninguna revisión independiente se autoaceptó.

## Evidencia reproducible

| Verificación | Resultado |
|---|---|
| `npm run test:unit` | 43 archivos, 258 pruebas, OK |
| `npm run typecheck` | OK |
| `npm run lint` | OK |
| `npm run build` | Next.js production build, OK |
| API en imagen local | 182 pruebas, OK |
| PostgreSQL/MinIO/Valkey real, runtime detenido | 391 pruebas, OK; 1 omitida por diseño |
| PostgreSQL focal de identidad administrada | 6 pruebas, OK |
| Replay del migrador | V0043 head, `applied: []`, `mutated: false` |
| Checksum V0043 | `424f03a246f00b9c9c22256b73f268c5d1dd729aa990fdb54f2efe1f1c51cd36` |
| `tools.runtime_config.validate` | 53 variables, OK |
| `tools.aws_private_pilot.validate` | contrato y fuentes válidos; despliegue/datos no autorizados |
| `tools.migration_readiness.validate` | V0001..V0043, OK |
| `tofu fmt -check` / `tofu validate` | formato y configuración AWS válidos con proveedor bloqueado 6.59.0 |
| golden registry | 14 casos, OK |
| mutation registry | 68 mutaciones / 9 validadores, OK |

La primera corrida PostgreSQL completa compitió con el worker local vivo y
falló en una reclamación de cola y un `tearDown` con FK. Se detuvieron solo
web/API/worker, se conservaron los servicios persistentes y el rerun exclusivo
de las 391 pruebas pasó. El runtime se volvió a levantar al terminar.

## Privilegios y privacidad

- `fincilia_app` no tiene acceso directo a las tablas legales o de identidad.
- `PUBLIC` no puede ejecutar la nueva función.
- La función pertenece a `fincilia_identity` (`NOLOGIN`), fija `search_path` y
  está declarada en el contrato de funciones `SECURITY DEFINER` con DB-G03
  pendiente.
- Correo y `sub` externos no se persisten en claro; se separan por propósito
  mediante HMAC.
- Una referencia de correo verificado solo puede pertenecer a un binding.
- Las versiones obsoletas fallan antes de cualquier estado parcial.

## Activaciones pendientes, no defectos ocultos

1. Comprar/verificar el dominio y decidir el hostname canónico.
2. Configurar Google Cloud Production, pantalla de consentimiento, dominio,
   home, privacidad y términos; obtener client ID/secret sin pegarlos en chat.
3. Guardar el secreto Google en Secrets Manager, aplicar OpenTofu y ejecutar la
   sonda live de identidad.
4. Obtener revisiones independientes Security, Privacy/Legal,
   Database/Architecture, Product/UX y QA.
5. Adjudicar assurance/step-up antes de acciones financieras de alto riesgo.
6. Superar DRG-00/DRG-01 antes de usar documentos financieros o datos reales.

## Rollback

- Operativo e inmediato: `FINCILIA_OIDC_REGISTRATION_MODE=disabled`. Solo cierra
  nuevas altas; no borra cuentas ni impide login.
- Identidad: retirar Google del app client/Hosted UI y conservar sujetos
  internos para investigación y recuperación controlada.
- Base: forward-only. V0043 no se modifica después de integrar; cualquier
  corrección usa V0044 o superior.

## Revisores requeridos

- Security: OIDC, HMAC, assurance, sesiones y privilegios.
- Privacy/Legal: textos y suficiencia de evidencia versionada.
- Database/Architecture: función privilegiada, unicidad y rollback forward.
- Product/UX: registro, errores y continuidad a primera empresa.
- QA: regresión, E2E live y accesibilidad sobre dominio final.

Hasta esas firmas, el estado correcto es `REVIEW_PENDING`.

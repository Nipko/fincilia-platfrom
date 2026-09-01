---
id: FNC-ONB-002
title: Registro autoservicio y primer espacio desde la web
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: f604c84
implementation_shas: [f3bbd4b, f4e553c, 93dac84]
tested_sha: b099c64
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Security, Backend/Architecture, Product/UX, Accessibility/QA]
---

# Resultado

Una persona que llega a `/entrar` puede crear una cuenta de prueba, una firma y
su membresia `owner`, iniciar sesion y continuar al alta transaccional de su
primera empresa sin semillas ni intervencion administrativa.

# Arquitectura autorizada para esta rebanada

- ADR-012 define la frontera entre identidad administrada y registro sintetico.
- Local y AWS T1 usan el proveedor local solo con `real_data_enabled=false` y
  nombres de usuario `@demo.local`.
- Ningun entorno con datos reales puede crear o autenticar credenciales locales.
- El producto crea sujeto, binding, firma y membresia en una sola transaccion;
  la empresa continua naciendo mediante FNC-ONB-001 en otra transaccion explicita.
- El rol runtime no recibe `INSERT` o `UPDATE` sobre credenciales. Una funcion
  acotada, propiedad de un rol `NOLOGIN`, materializa exclusivamente el alta.

# Rutas

- `db/migrations/V0039*`, bootstrap local/T1 y pruebas PostgreSQL relacionadas.
- `packages/platform/python/fincilia_platform/identity.py`.
- `apps/api/src/fincilia_api/registration.py`, rutas y pruebas de identidad.
- `apps/web/src/app/registro/**`, entrada publica, acciones/API y pruebas web.
- ADR-012, contrato de migraciones, CI, catalogo, handoff y registros centrales.

# Criterios de aceptacion

1. Registro atomico de subject, identity binding, credential, firm y membership owner.
2. Email sintetico normalizado y restringido a `@demo.local`; duplicados no dejan filas.
3. Password de 14–128 caracteres con mayuscula, minuscula, numero y simbolo; solo se
   persiste PBKDF2-SHA256 con sal aleatoria y 240.000 iteraciones.
4. API no registra, refleja ni audita correo, password, sal o hash.
5. `fincilia_app` no puede escribir directamente identidad o credenciales y `PUBLIC`
   no puede ejecutar la funcion privilegiada.
6. La respuesta crea una sesion corta y redirige a `/empresas/nueva`.
7. El usuario completa empresa, cuenta, fuente y ciclo con el flujo existente.
8. Registro duplicado, payload extra, entorno real, throttling y fallo intermedio
   se rechazan sin enumeracion ni estado parcial.
9. PostgreSQL, API, web, E2E, accesibilidad y quality gate pasan.
10. AWS T1 se publica por digest y se valida solo con datos completamente sinteticos.

# Fuera de alcance

En esta rebanada histórica quedaron fuera autorregistro Cognito, correo real,
OAuth social y aceptación legal. FNC-IAM-004 los sustituye para el recorrido
Google definitivo sin contraseñas propias. Cobro, datos reales y mover
DRG-00/DRG-01 continúan fuera de alcance.

# Cierre técnico

El recorrido histórico queda cerrado para el laboratorio sintético local y se
entrega a revisión independiente. Cinco contratos API y dos pruebas focales de
acciones web pasaron en la revalidación; el CI integral `33473978646` sobre
`b099c64` cubre además esquema vacío, PostgreSQL, Chromium y Axe. El acceso
público final no reutiliza contraseñas locales: FNC-IAM-004 lo sustituye por
Google/Cognito y aceptación legal versionada.

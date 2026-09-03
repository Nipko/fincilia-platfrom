# Publicación de Google OAuth para Fincilia

Estado: **dominio y recorrido preparados para revisión, alta aún protegida**. Este runbook configura
Google como proveedor social de Amazon Cognito y permite alta publica sin
invitaciones, sin convertir claims externos en roles de Fincilia. La activacion
con personas reales permanece bloqueada por DRG-00 y revision independiente;
publicar las paginas y preparar el proyecto no mueve ese gate.

### Estado observado — 2026-09-03

- `https://fincilia.com` responde por HTTPS y publica portada, privacidad,
  terminos y eliminacion sin exigir sesion.
- Google existe como proveedor social del User Pool y solicita unicamente
  `openid email profile`.
- El cliente Cognito exclusivo de Fincilia esta administrado por OpenTofu, no
  genera secret, admite solo `Google` y tiene revocacion habilitada.
- Redirect de Google:
  `https://fincilia-t0-632144225293.auth.sa-east-1.amazoncognito.com/oauth2/idpresponse`.
- Callback de Fincilia:
  `https://fincilia.com/api/auth/callback/cognito`.
- Logout de Fincilia: `https://fincilia.com/entrar`.
- Responsable publicado: Parallext LLC. Soporte: `support@fincilia.com`;
  privacidad: `privacy@fincilia.com`; contacto de desarrollador:
  `security@fincilia.com`.
- El centro legal público se presenta en inglés para la revisión de marca y
  conserva sus rutas estables en `fincilia.com`.
- Versiones activas preparadas para nuevas altas: `terms-2026-09-03-en` y
  `privacy-2026-09-03-en`.
- El runtime permanece deshabilitado. Esta preparacion no adjudica DRG-00 ni
  autoriza que una identidad personal complete el flujo.

## 1. Lo que debe entregar el Founder

No enviar secretos por chat, Git, capturas, handoffs ni variables de Terraform.

| Dato | Ejemplo de forma | Uso |
| --- | --- | --- |
| Dominio final del servicio | `fincilia.com` | Portada, políticas y callback de Fincilia |
| Cuenta Google Cloud | cuenta con rol Owner/Editor | Crear proyecto y OAuth client |
| Propiedad Search Console | dominio raíz verificado | Demostrar control del dominio autorizado |
| Correo de soporte | `support@fincilia.com` | Consent screen y contacto de usuarios |
| Correo de desarrollador | `security@fincilia.com` | Avisos de Google |
| Logo de Fincilia | archivo cuadrado según el límite que muestre Google | Branding; no usar una marca de Google |

Nombre público: **Fincilia**. Operador: **Parallext LLC**. Desarrollo:
**Parallext.com**. El Client ID se
puede compartir con el implementador por un canal controlado; el Client Secret
se carga directamente en AWS y nunca se copia al repositorio.

## 2. Matriz de URLs exactas

Esquema, mayúsculas, ruta y slash final forman parte de la identidad de una URI
y deben coincidir exactamente.

| Destino | Valor |
| --- | --- |
| Portada pública | `https://fincilia.com/` |
| Privacidad | `https://fincilia.com/privacy` |
| Términos | `https://fincilia.com/terms` |
| Cookies | `https://fincilia.com/cookies` |
| Seguridad | `https://fincilia.com/security` |
| DPA | `https://fincilia.com/dpa` |
| Subencargados | `https://fincilia.com/subprocessors` |
| Eliminación de cuenta | `https://fincilia.com/delete-account` |
| Origen JavaScript en Google | `https://fincilia-t0-632144225293.auth.sa-east-1.amazoncognito.com` |
| Redirect URI en Google | `https://fincilia-t0-632144225293.auth.sa-east-1.amazoncognito.com/oauth2/idpresponse` |
| Callback de Cognito a Fincilia | `https://fincilia.com/api/auth/callback/cognito` |
| Logout de Cognito | `https://fincilia.com/entrar` |

El redirect de **Google** termina en Cognito. El callback de **Cognito** termina
en Fincilia. Intercambiarlos produce `redirect_uri_mismatch` o expone el flujo a
un cliente que no debe redimir el código de Google.

Las rutas anteriores `/privacidad`, `/terminos`, `/seguridad`,
`/subencargados` y `/eliminar-cuenta` existen solo como redirecciones HTTP 308.
No deben registrarse en una configuración nueva de Google.

Los valores desplegados se obtienen sin secretos con:

```text
tofu -chdir=infra/aws/private-pilot output -json cognito
```

`hosted_ui_domain` aporta el origen Cognito; se le agrega
`/oauth2/idpresponse` solamente en Google. `callback_uri` es el callback de la
aplicación y ya está fijado por el contrato de infraestructura.

## 3. Publicar primero el dominio de confianza

1. Publicar el mismo build de Fincilia por HTTPS en `fincilia.com`.
2. Confirmar que `/`, `/privacy`, `/terms` y `/delete-account` responden
   sin login, sin redirección a otro dominio y con certificado válido.
3. La portada debe describir Fincilia, enlazar privacidad/términos y explicar que
   Google solo entrega identificador, nombre y correo verificado para autenticar.
4. Verificar el dominio raíz en Google Search Console con la misma cuenta que es
   Owner o Editor del proyecto Google Cloud.
5. Agregar el dominio registrable —no la URL completa— a `Authorized domains`.

Estas páginas se sirven desde la aplicación Next.js existente. No requieren S3,
CloudFront ni otro servicio AWS separado: el costo incremental de **las páginas**
es cero sobre el runtime ya encendido. Siguen existiendo los costos del dominio,
del runtime, almacenamiento, secretos y transferencia del servicio.

## 4. Configurar Google Auth Platform

Crear proyectos separados para preproducción y producción. El cliente que se
publica para usuarios finales pertenece al proyecto de producción. En Google
Cloud Console:

1. Abrir **Google Auth Platform → Branding**.
2. App name: `Fincilia`.
3. User support email: el buzón atendido del Founder/soporte.
4. Homepage: `https://fincilia.com/`.
5. Privacy policy: `https://fincilia.com/privacy`.
6. Terms of service: `https://fincilia.com/terms`.
7. Authorized domain: el dominio raíz verificado en Search Console.
8. Developer contact: el correo atendido de Parallext.com.
9. En **Audience**, seleccionar `External`. Durante la configuracion inicial se
   puede usar `Testing`; antes de abrir registro cambiar el proyecto definitivo
   a `In production`. En ese estado cualquier cuenta Google puede autenticarse
   y ya no existe una lista de invitados de Fincilia.
10. En **Data Access**, declarar solamente `openid`,
    `https://www.googleapis.com/auth/userinfo.email` y
    `https://www.googleapis.com/auth/userinfo.profile`.
11. En **Clients**, crear `Web application` con nombre
    `Fincilia web production`.
12. Authorized JavaScript origin: el origen Cognito de la matriz.
13. Authorized redirect URI: el endpoint Cognito `/oauth2/idpresponse` de la
   matriz. No agregar callbacks locales al proyecto de producción.
14. Guardar Client ID. Cargar el Client Secret directamente en el secreto AWS
    `fincilia/private-pilot/google-oidc-v1`; no descargarlo al repositorio.

Fincilia no habilita Drive, Gmail, Calendar, Contacts ni ninguna API de negocio
de Google. Si una funcionalidad futura requiere otro scope, se trata como una
decisión y verificación separadas; no se amplía este cliente silenciosamente.

## 5. Conectar Google a Cognito

En el User Pool de Fincilia:

1. Abrir **Social and external providers** y crear el proveedor `Google`.
2. Introducir el Client ID y Client Secret del mismo cliente web.
3. Authorized scopes: `openid email profile`.
4. Mapear `sub` a la identidad externa de Cognito, `email` a `email`,
   `email_verified` a `email_verified` y `name` a `name`. No mapear empresa,
   firma, permisos ni roles.
5. Agregar `Google` a los identity providers soportados por el app client web,
   conservando Authorization Code, PKCE y el callback exacto de la matriz.
6. Mantener tokens de acceso/ID en 15 minutos y revocación habilitada. Fincilia
   descarta el refresh token y no lo persiste.
7. Mantener deshabilitado el `SignUp` nativo del User Pool. El acceso social
   crea el perfil federado; la cuenta Fincilia solo nace cuando la persona inicia
   el recorrido explícito de registro, acepta las versiones legales vigentes y
   Google devuelve un correo verificado.
8. Configurar el runtime con issuer/endpoints/client ID de Cognito y mantener
   `FINCILIA_OIDC_ENABLED=false` hasta la adjudicación de DRG-00.

`mfa_configuration = ON` protege el flujo nativo de Cognito. No debe presentarse
como evidencia de MFA para Google: en federación, los factores se delegan a
Google y los scopes mínimos de esta integración no prueban segundo factor. Se
recomienda a cada persona habilitar verificación en dos pasos, pero esa es una
condición operativa, no una garantía que Fincilia pueda certificar. La
decisión de assurance queda registrada como `UD-IAM-FEDERATED-MFA`.

El secret ya tiene un contenedor dedicado en AWS Secrets Manager. La
configuración del proveedor se hace fuera del estado OpenTofu para impedir que el
Client Secret termine en el state o en un plan guardado.

## 6. Prueba y publicación gradual

No se crean, distribuyen ni conservan invitaciones. La apertura y cierre del
alta es un control operativo: `FINCILIA_OIDC_REGISTRATION_MODE=public_google`
permite cuentas nuevas y `disabled` conserva el login de las existentes. Cambiar
ese control no elimina sujetos, firmas, membresías ni aceptaciones.

### Recorrido de aceptación

Después de conectar Google y antes de abrir el registro, ejecutar la sonda
contra el control plane. Los tres identificadores no son secretos y se obtienen
del output `cognito` de OpenTofu; no usar esta orden con credenciales root.

```text
python -m tools.identity_readiness.cli \
  --profile fincilia-sandbox \
  --region sa-east-1 \
  --user-pool-id <USER_POOL_ID> \
  --client-id <WEB_CLIENT_ID> \
  --domain-prefix <COGNITO_DOMAIN_PREFIX> \
  --app-origin https://fincilia.com
```

Exit `0` significa que los 16 controles de configuración observables pasan;
`10`, que la consulta fue válida pero al menos uno no está listo; `2`, que la
evidencia no pudo obtenerse. El informe omite IDs, usuarios, correos y secretos,
y siempre conserva `activation_authorized: false` y
`real_data_authorized: false`: una sonda técnica no adjudica DRG-00.

1. Probar primero con una identidad Google controlada en el proyecto de
   preproducción y repetir en el proyecto definitivo `In production`.
2. Confirmar `state`, nonce, PKCE, issuer, audience, expiración y correo
   verificado; un fallo no debe crear sujeto, firma ni empresa.
3. Confirmar que un `login` desconocido no crea filas y dirige a `/registro`.
   Confirmar alta nueva completa, dos aceptaciones legales versionadas y login
   idempotente. Al pulsar `Salir`, verificar
   que desaparecen las tres cookies Fincilia y Cognito vuelve exactamente a
   `https://fincilia.com/entrar`; volver a entrar debe iniciar un flujo nuevo.
4. Cambiar temporalmente el modo de registro a `disabled` y comprobar que no
   nacen cuentas nuevas mientras las existentes siguen entrando. Suspender la
   identidad de prueba en Cognito y retirar sus grants en Fincilia; ambas
   capas deben negar el siguiente acceso sin aceptar claims de empresa del IdP.
5. Confirmar que URLs, logs, auditoría y base no contienen códigos, tokens,
   correo ni `sub` en claro.
6. Ejecutar regresión de rutas públicas, onboarding, aislamiento multiempresa y
   recuperación ante proveedor no disponible.
7. Obtener revisiones nominales de Security, Privacy/Legal, Architecture y QA.
8. Antes de abrir registro, mover el proyecto definitivo a `In production`,
   verificar branding y completar cualquier revisión que Google solicite. Los
   proyectos de preproducción y producción deben permanecer separados.

## 7. Fuentes normativas y técnicas

- [Políticas OAuth 2.0 de Google](https://developers.google.com/identity/protocols/oauth2/policies)
- [Preparación y verificación de marca](https://developers.google.com/identity/protocols/oauth2/production-readiness/brand-verification)
- [Requisitos de verificación](https://support.google.com/cloud/answer/13464321)
- [Audiencia y estado Testing](https://support.google.com/cloud/answer/15549945)
- [Guía de marca del botón Google](https://developers.google.com/identity/branding-guidelines)
- [Proveedor social Google en Cognito](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-social-idp.html)
- [Endpoints de federación Cognito](https://docs.aws.amazon.com/cognito/latest/developerguide/federation-endpoints.html)

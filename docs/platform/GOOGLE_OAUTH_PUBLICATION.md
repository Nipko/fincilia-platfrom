# Publicación de Google OAuth para Fincilia

Estado: **preparado, no activado**. Este runbook configura Google como proveedor
social de Amazon Cognito sin convertir claims externos en roles de Fincilia. La
activación con personas reales permanece bloqueada por DRG-00 y revisión
independiente; publicar las páginas y preparar el proyecto no mueve ese gate.

## 1. Lo que debe entregar el Founder

No enviar secretos por chat, Git, capturas, handoffs ni variables de Terraform.

| Dato | Ejemplo de forma | Uso |
| --- | --- | --- |
| Dominio final de la beta | `beta.<dominio-propio>` | Portada, políticas y callback de Fincilia |
| Cuenta Google Cloud | cuenta con rol Owner/Editor | Crear proyecto y OAuth client |
| Propiedad Search Console | dominio raíz verificado | Demostrar control del dominio autorizado |
| Correo de soporte | buzón atendido | Consent screen y contacto de usuarios |
| Correo de desarrollador | buzón atendido | Avisos de Google |
| Usuarios de prueba | correos de los invitados | Audience `Testing`, máximo 100 |
| Logo de Fincilia | archivo cuadrado según el límite que muestre Google | Branding; no usar una marca de Google |

Nombre público: **Fincilia**. Desarrollador: **Parallext.com**. El Client ID se
puede compartir con el implementador por un canal controlado; el Client Secret
se carga directamente en AWS y nunca se copia al repositorio.

## 2. Matriz de URLs exactas

Reemplazar únicamente los dos marcadores. Esquema, mayúsculas, ruta y slash
final forman parte de la identidad de una URI y deben coincidir exactamente.

| Destino | Valor |
| --- | --- |
| Portada pública | `https://<APP_DOMAIN>/` |
| Privacidad | `https://<APP_DOMAIN>/privacidad` |
| Términos | `https://<APP_DOMAIN>/terminos` |
| Eliminación de cuenta | `https://<APP_DOMAIN>/eliminar-cuenta` |
| Origen JavaScript en Google | `https://<COGNITO_DOMAIN>.auth.sa-east-1.amazoncognito.com` |
| Redirect URI en Google | `https://<COGNITO_DOMAIN>.auth.sa-east-1.amazoncognito.com/oauth2/idpresponse` |
| Callback de Cognito a Fincilia | `https://<APP_DOMAIN>/api/auth/callback/cognito` |
| Logout de Cognito | `https://<APP_DOMAIN>/entrar` |

El redirect de **Google** termina en Cognito. El callback de **Cognito** termina
en Fincilia. Intercambiarlos produce `redirect_uri_mismatch` o expone el flujo a
un cliente que no debe redimir el código de Google.

Los valores desplegados se obtienen sin secretos con:

```text
tofu -chdir=infra/aws/private-pilot output -json cognito
```

`hosted_ui_domain` aporta el origen Cognito; se le agrega
`/oauth2/idpresponse` solamente en Google. `callback_uri` es el callback de la
aplicación y ya está fijado por el contrato de infraestructura.

## 3. Publicar primero el dominio de confianza

1. Publicar el mismo build de Fincilia por HTTPS en `<APP_DOMAIN>`.
2. Confirmar que `/`, `/privacidad`, `/terminos` y `/eliminar-cuenta` responden
   sin login, sin redirección a otro dominio y con certificado válido.
3. La portada debe describir Fincilia, enlazar privacidad/términos y explicar que
   Google solo entrega identificador, nombre y correo verificado para autenticar.
4. Verificar el dominio raíz en Google Search Console con la misma cuenta que es
   Owner o Editor del proyecto Google Cloud.
5. Agregar el dominio registrable —no la URL completa— a `Authorized domains`.

Estas páginas se sirven desde la aplicación Next.js existente. No requieren S3,
CloudFront ni otro servicio AWS separado: el costo incremental de **las páginas**
es cero sobre el runtime ya encendido. Siguen existiendo los costos del dominio,
del runtime, almacenamiento, secretos y transferencia de la beta.

## 4. Configurar Google Auth Platform

Crear un proyecto separado para esta beta; no reutilizar el futuro proyecto de
producción. En Google Cloud Console:

1. Abrir **Google Auth Platform → Branding**.
2. App name: `Fincilia`.
3. User support email: el buzón atendido del Founder/soporte.
4. Homepage: `https://<APP_DOMAIN>/`.
5. Privacy policy: `https://<APP_DOMAIN>/privacidad`.
6. Terms of service: `https://<APP_DOMAIN>/terminos`.
7. Authorized domain: el dominio raíz verificado en Search Console.
8. Developer contact: el correo atendido de Parallext.com.
9. En **Audience**, seleccionar `External` y mantener `Testing` para la beta
   cerrada. Añadir únicamente los invitados nominales; Google limita Testing a
   100 usuarios y sus autorizaciones vencen a los siete días.
10. En **Data Access**, declarar solamente `openid`,
    `https://www.googleapis.com/auth/userinfo.email` y
    `https://www.googleapis.com/auth/userinfo.profile`.
11. En **Clients**, crear `Web application` con nombre
    `Fincilia beta web`.
12. Authorized JavaScript origin: el origen Cognito de la matriz.
13. Authorized redirect URI: el endpoint Cognito `/oauth2/idpresponse` de la
    matriz. No agregar callbacks locales al proyecto de beta.
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
7. Configurar el runtime con issuer/endpoints/client ID de Cognito y mantener
   `FINCILIA_OIDC_ENABLED=false` hasta la adjudicación de DRG-00.

El secret ya tiene un contenedor dedicado en AWS Secrets Manager. La
configuración del proveedor se hace fuera del estado OpenTofu para impedir que el
Client Secret termine en el state o en un plan guardado.

## 6. Prueba y publicación gradual

### Operar invitaciones nominales

La invitación se crea desde una sesión privada del migrador, con
`FINCILIA_MIGRATOR_URL` y `FINCILIA_IDENTITY_BINDING_HMAC_KEY` inyectadas desde
Secrets Manager. No escribir sus valores en la línea de comandos ni exportarlos
a un fichero. El correo se introduce en el prompt oculto y PostgreSQL recibe
solo su HMAC; el código aparece una vez en stdout para entregarlo por un canal
distinto a la cuenta Google invitada.

```text
python -m db.admin.pilot_invitations create --hours 168
python -m db.admin.pilot_invitations list
python -m db.admin.pilot_invitations revoke --invitation <UUID>
```

No redirigir la salida de `create`, no capturar la terminal y no pegar el código
en tickets, chats de agentes, Git o logs. `list` expone únicamente identificador,
prefijo del digest y marcas de estado; `revoke` solo acepta el UUID de la
invitación. Las invitaciones locales sintéticas se administran con
`db.admin.invitations` y no son válidas en el piloto nominal.

### Recorrido de aceptación

1. Probar con una sola identidad nominal de Testing y una invitación de un uso.
2. Confirmar `state`, nonce, PKCE, issuer, audience, expiración y correo
   verificado; un fallo no debe crear sujeto, firma ni empresa.
3. Confirmar alta nueva completa y login idempotente. Al pulsar `Salir`, verificar
   que desaparecen las tres cookies Fincilia y Cognito vuelve exactamente a
   `https://<APP_DOMAIN>/entrar`; volver a entrar debe iniciar un flujo nuevo.
4. Revocar una invitación no consumida y comprobar que no crea filas. Suspender
   la identidad de prueba en Cognito y retirar sus grants en Fincilia; ambas
   capas deben negar el siguiente acceso sin aceptar claims de empresa del IdP.
5. Confirmar que URLs, logs, auditoría y base no contienen códigos, tokens,
   correo ni `sub` en claro.
6. Ejecutar regresión de rutas públicas, onboarding, aislamiento multiempresa y
   recuperación ante proveedor no disponible.
7. Obtener revisiones nominales de Security, Privacy/Legal, Architecture y QA.
8. Para una publicación pública futura, mover el proyecto de producción a
   `In production`, verificar branding y completar cualquier revisión que Google
   solicite. La beta y producción deben usar proyectos Google separados.

## 7. Fuentes normativas y técnicas

- [Políticas OAuth 2.0 de Google](https://developers.google.com/identity/protocols/oauth2/policies)
- [Preparación y verificación de marca](https://developers.google.com/identity/protocols/oauth2/production-readiness/brand-verification)
- [Requisitos de verificación](https://support.google.com/cloud/answer/13464321)
- [Audiencia y estado Testing](https://support.google.com/cloud/answer/15549945)
- [Guía de marca del botón Google](https://developers.google.com/identity/branding-guidelines)
- [Proveedor social Google en Cognito](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-social-idp.html)
- [Endpoints de federación Cognito](https://docs.aws.amazon.com/cognito/latest/developerguide/federation-endpoints.html)

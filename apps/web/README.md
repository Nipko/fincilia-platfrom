# Fincilia Web

Interfaz local de Fincilia: Next.js con App Router y TypeScript estricto.

## La regla que ordena todo el codigo

**La web nunca autoriza.** No hay una copia de la matriz de permisos en el
cliente; se pinta lo que el servidor devuelve, y un `403` se ensena como «sin
acceso». Si alguna vez esta interfaz decidiera algo, existirian dos verdades
sobre quien puede hacer que, y solo una estaria protegida por RLS.

Consecuencia concreta: **el token nunca llega al navegador.** Entra en una cookie
`httpOnly` con `SameSite=Strict` y sale de ella dentro del proceso de Next, que
es quien llama a la API. Un token en `localStorage` estaria al alcance de
cualquier script de la pagina.

## Correr

Va dentro del stack local, no suelto:

~~~bash
docker compose -f infra/local/compose.yaml -p fincilia-local up -d --wait
~~~

Despues de migrar y sembrar, en <http://127.0.0.1:53000>. Los usuarios de demo y
la contrasena sintetica los crea `db/seed/local.py`; estan documentados en
[`docs/platform/LOCAL_DEVELOPMENT.md`](../../docs/platform/LOCAL_DEVELOPMENT.md).

## Comprobar

~~~bash
docker compose -f infra/local/compose.yaml -p fincilia-local run --rm --no-deps web npm run typecheck
docker compose -f infra/local/compose.yaml -p fincilia-local run --rm --no-deps web npm run lint
cd apps/web
npm ci --ignore-scripts
npm run test:unit
npx --no-install playwright install chromium
FINCILIA_E2E_BASE_URL=http://127.0.0.1:53000 npm run test:e2e
FINCILIA_E2E_BASE_URL=http://127.0.0.1:53000 npm run test:a11y
~~~

## Configuracion

| Variable | Para que |
|---|---|
| `FINCILIA_API_BASE_URL` | base de la API; sin ella el proceso no arranca, en vez de adivinar un `localhost` que en un contenedor no existe |
| `FINCILIA_WEB_SECURE_COOKIES` | `true` solo con origen https; una cookie `secure` sobre http no se guarda |
| `FINCILIA_PUBLIC_ORIGIN` | origen HTTPS exacto de la web; obligatorio para identidad administrada |
| `FINCILIA_OIDC_AUTHORIZE_ENDPOINT` | endpoint `/oauth2/authorize` exacto del dominio Cognito |
| `FINCILIA_OIDC_CLIENT_ID` | app client publico de Cognito, sin client secret |
| `FINCILIA_OIDC_REDIRECT_URI` | callback HTTPS exacto de esta web |
| `FINCILIA_OAUTH_TRANSACTION_KEY` | clave AES-256 dedicada para la cookie OAuth transitoria; solo Secrets Manager |

## Que se puede hacer hoy

Entrar, ver la firma y las empresas con acceso vigente; administrar cuentas,
fuentes y ciclos; subir evidencia por una fuente; revisar su perfil; mapear
columnas; preparar una version canonica; y navegar sus movimientos y linaje. Todo
usa datos sinteticos y conserva las decisiones financieras en la API.

El formulario de subida solo aparece cuando el servidor concede el permiso. El
navegador envia el documento a un BFF same-origin por streaming; el token
`httpOnly` nunca entra en JavaScript. La API vuelve a validar permiso, fuente,
tipo y el limite exacto de 25 MiB.

## Lo que todavia no hay

Conciliacion P4, excepciones contables, informes y cierre autorizado. La interfaz
actual llega hasta movimientos canonicos para revision; no hace auto-match ni
declara un cierre.

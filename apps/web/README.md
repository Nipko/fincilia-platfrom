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
~~~

## Configuracion

| Variable | Para que |
|---|---|
| `FINCILIA_API_BASE_URL` | base de la API; sin ella el proceso no arranca, en vez de adivinar un `localhost` que en un contenedor no existe |
| `FINCILIA_WEB_SECURE_COOKIES` | `true` solo con origen https; una cookie `secure` sobre http no se guarda |

## Que se puede hacer hoy

Entrar, ver la firma y las empresas con acceso vigente, abrir una y ver sus roles,
sus permisos, sus documentos y su auditoria; y subir un extracto o un soporte, si
el rol incluye `document.upload`.

El formulario de subida solo aparece cuando el servidor dice que ese permiso
esta. No es la comprobacion: la comprobacion la hace la API y volveria a denegar.
Ocultarlo evita ofrecer una accion que va a fallar.

## Lo que todavia no hay

Mapping, conciliacion, reglas, informes y cierre. La interfaz llega hasta la
evidencia almacenada; lo que se hace con ella todavia no existe.

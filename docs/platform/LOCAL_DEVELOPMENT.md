# Entorno local de Fincilia

| Campo | Valor |
|---|---|
| Tareas | FNC-PLT-002 (base), **FNC-PLT-008** (stack de producto) |
| Estado | Review pending |
| Datos | Exclusivamente sintéticos |
| Contrato ejecutable | `tools/local_stack` |
| Proyecto Compose | `fincilia-local` |

---

## 1. Levantar todo

Un solo comando, desde la raíz del repositorio:

```bash
docker compose -f infra/local/compose.yaml -p fincilia-local up -d --wait
```

Cuando termina con exit `0`, los cinco servicios están **healthy**: `postgres`,
`valkey`, `objectstore`, `api` y `worker`. `--wait` no vuelve hasta que cada
healthcheck pasa, así que un `0` aquí significa que el stack sirve, no que los
contenedores arrancaron.

Comprobación de un vistazo:

```bash
curl -s http://127.0.0.1:58080/health/ready
```

```json
{"status":"ready","dependencies":[
  {"name":"postgresql","status":"up","detail":"fincilia_app@17.11"},
  {"name":"valkey","status":"up","detail":"pong"},
  {"name":"object_storage","status":"up","detail":"4 buckets"}]}
```

### Aplicar el esquema

El stack arranca sano con la base vacía: `/health/ready` sólo dice que PostgreSQL
responde. Para que exista esquema hay que migrar, **a mano y una vez**:

```bash
docker compose -f infra/local/compose.yaml -p fincilia-local --profile migrate run --rm migrate
```

```json
{"applied": ["V0001"], "head": "V0001", "mutated": true, "ok": true}
```

Repetirlo devuelve `"mutated": false`. Las migraciones no corren en el arranque de
la API a propósito: un servicio que migra al arrancar migra una vez por réplica, y
convierte un despliegue en un cambio de esquema. Detalle en [`db/README.md`](../../db/README.md).

### Sembrar la demo y entrar

```bash
docker compose -f infra/local/compose.yaml -p fincilia-local --profile migrate run --rm migrate python -m db.seed.local
```

Crea una firma (**Contadores Andes SAS**) y dos empresas sintéticas
(**Panaderia La Espiga SAS** y **Transportes Andinos SAS**), con cuatro usuarios
locales. Es idempotente y determinista: repetirlo devuelve `"mutated": false`, y
los identificadores son los mismos en cualquier máquina.

| Usuario | Rol en Espiga | Rol en Andinos |
|---|---|---|
| `sofia@demo.local` | owner | owner |
| `ana@demo.local` | preparer | preparer |
| `beto@demo.local` | reviewer | — |
| `carla@demo.local` | — | auditor |

La contraseña de todos es `fincilia-demo-only`, o lo que diga
`FINCILIA_LOCAL_DEMO_SECRET`. **Es sintética**: no abre nada más que este stack, y
la tabla `local_credential` sólo existe en el entorno local.

Ana prepara y Beto revisa a propósito: nadie propone y confirma la misma
conciliación. La segregación de funciones se ve en los permisos que devuelve el
servidor, no en una nota del manual.

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:58080/api/v1/auth/session   -H 'content-type: application/json'   -d '{"username":"ana@demo.local","secret":"fincilia-demo-only"}' | jq -r .token)
curl -s http://127.0.0.1:58080/api/v1/me -H "Authorization: Bearer $TOKEN" | jq
```

Bajar sin perder datos:

```bash
docker compose -f infra/local/compose.yaml -p fincilia-local down
```

Empezar de cero, **borrando** los volúmenes locales:

```bash
docker compose -f infra/local/compose.yaml -p fincilia-local down --volumes
```

---

## 2. Qué corre y dónde

| Servicio | Imagen | Puerto en el host | Papel |
|---|---|---|---|
| `postgres` | `postgres:17.11-alpine3.24@sha256:18cfe3ef…` | — | autoridad financiera |
| `valkey` | `valkey/valkey:8.1-alpine@sha256:e0eb7c48…` | — | caché, locks efímeros, progreso |
| `objectstore` | `minio/minio:RELEASE.2025-04-22@sha256:a1ea29fa…` | `127.0.0.1:59000`, consola `59001` | zonas de evidencia |
| `api` | construida de `apps/api/Dockerfile` | `127.0.0.1:58080` | FastAPI |
| `worker` | construida de `workers/document/Dockerfile` | — | procesamiento de documentos |

Toda imagen está fijada **por digest**. Una etiqueta puede reapuntarse a otros
bytes sin cambiar de nombre, y entonces «reproducible» deja de significar nada.

### Por qué la base de datos no tiene puerto en el host

Hay dos redes:

- `fincilia_local_private` es `internal: true` y **no tiene salida a internet**. Si
  un fichero subido consiguiera ejecutar algo, no tiene a dónde llamar.
- `fincilia_local_edge` existe solo para `api` y `objectstore`, que el navegador
  necesita alcanzar.

Docker **ignora la publicación de puertos en una red `internal`**. Publicar el
puerto de postgres obligaría a moverlo a la red con salida, y la base de datos es
justo donde eso menos conviene. El `127.0.0.1:55430` que declaraba la versión
anterior de este fichero nunca funcionó por esa razón; se retiró en vez de dejarlo
como documentación falsa.

Para entrar a la base:

```bash
docker compose -f infra/local/compose.yaml -p fincilia-local exec postgres \
  psql -U fincilia_local_admin -d fincilia_local
```

El worker vive **solo** en la red privada: es quien toca contenido no confiable, y
el validador `tools/local_stack` falla si alguien lo pone en la red con salida.

---

## 3. Configuración

Copia `.env.example` a `.env` y déjalo sin versionar. Cada variable declarada allí
existe en `docs/platform/runtime-config.json`; el validador falla si una de las dos
listas se mueve sin la otra.

Tres reglas del arranque:

- **Sin defaults para credenciales.** Si falta una, el proceso no arranca. Un
  default silencioso es como se acaba conectando un entorno a la base equivocada.
- **`FINCILIA_ENV` solo acepta `local` o `test`.** `production` no es un valor
  posible en este binario.
- **`FINCILIA_REAL_DATA_ENABLED`, `FINCILIA_AI_GATEWAY_ENABLED` y
  `FINCILIA_PAYMENTS_ENABLED` en `true` hacen fallar el arranque**, no imprimen una
  advertencia. Encenderlas es una decisión humana con gate.

El worker **rechaza** recibir `FINCILIA_AUTH_SIGNING_KEY`: no emite ni valida
tokens, y un secreto que un proceso no usa sigue estando en su entorno y en sus
volcados.

---

## 4. Zonas de evidencia

La API crea las cuatro al arrancar, de forma idempotente, **solo** cuando el
entorno es `local`:

| Bucket | Contenido |
|---|---|
| `fincilia-quarantine` | lo recién subido, antes de inspeccionar |
| `fincilia-raw` | evidencia inmutable, con versionado activado |
| `fincilia-derived` | derivaciones versionadas |
| `fincilia-exports` | exportaciones auditadas |

En un despliegue real esto es trabajo de infraestructura y el servicio recibe
credenciales sin permiso de creación.

---

## 5. Pruebas

```bash
# Contratos compartidos: solo biblioteca estandar, sin levantar nada
python -m unittest discover -s packages/contracts/python -t packages/contracts/python

# Contrato del stack
python -m tools.local_stack.validate
python -m unittest tools.local_stack.test_validate

# API: dentro de su imagen, que es donde viven sus dependencias
docker compose -f infra/local/compose.yaml -p fincilia-local run --rm --no-deps \
  api python -m unittest discover -s /app/tests -t /app/tests

# Esquema: plan sin base, y aislamiento contra PostgreSQL real
docker compose -f infra/local/compose.yaml -p fincilia-local --profile migrate   run --rm migrate python -m unittest discover -s /app/db/tests -t /app

# Contrato del fichero de migraciones
python -m unittest tools.migration_readiness.test_validate

# Ciclo de vida de persistencia (perfil test)
docker compose -f infra/local/compose.yaml -p fincilia-local --profile test \
  run --rm lifecycle-test initial
```

---

## 6. Diagnóstico

| Síntoma | Qué mirar |
|---|---|
| `up --wait` no vuelve | `docker compose … ps` y `logs <servicio>`; el healthcheck dice quién falta |
| `/health/ready` da 503 | el cuerpo nombra la dependencia caída y por qué |
| la API no arranca | casi siempre configuración: el error de pydantic nombra el campo |
| el worker sale con 1 | no alcanzó alguna dependencia en 30 s; no se declara sano si no puede trabajar |
| `/health/ready` dice `schema: down` | falta migrar, o la imagen espera otra cabeza que la base |
| `401` con token recién emitido | los permisos de esa empresa cambiaron después de emitirlo; vuelve a entrar |
| `403` en una empresa que existe | no hay concesión viva, o la delegación de la firma está revocada |
| puerto ocupado | cambia `FINCILIA_LOCAL_API_PORT` o `FINCILIA_LOCAL_OBJECT_PORT` en `.env` |

`/health/live` no toca ninguna dependencia: si consultara la base, un fallo de red
reiniciaría el contenedor sin motivo. `/health/ready` sí las consulta, porque
responde a otra pregunta.

---

## 7. Límites honestos

1. Un stack sano dice que los servicios responden, **no** que el producto sea
   correcto. Con la base sin migrar, `/health/live` sigue en 200 y `/health/ready`
   da 503 nombrando el esquema.
2. El esquema local está habilitado por `local_build` en
   `docs/database/migration-tooling.json`, que es un alcance **solo local**: no
   acepta ADR-002, no selecciona herramienta, no aprueba S1 ni autoriza ningún
   entorno compartido.
3. Todo dato es sintético. `real_data_enabled` sigue apagado por contrato.
4. No hay despliegue, ni cloud, ni proveedor externo, ni pagos.
5. El `.env.example` contiene ejemplos seguros; las credenciales reales no viven en
   el repositorio ni en la imagen.

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
sh infra/local/up.sh
```

Cuando termina, la web está en <http://127.0.0.1:53000> y se entra como
`ana@demo.local`.

El script hace tres cosas en un orden que **no** es un detalle de
implementación: levanta la infraestructura, migra y siembra, y sólo después
arranca las aplicaciones. Es el mismo orden que en un despliegue real, y aquí es
obligatorio porque las aplicaciones se niegan a declararse sanas contra una base
sin esquema: el worker sale con `1` antes que reportar salud sin poder trabajar,
y `/health/ready` devuelve 503 nombrando el esquema. Un `docker compose up -d
--wait` a secas sobre una base vacía falla, y falla a propósito.

> **Si tu volumen local es anterior a `V0005`**, recréalo: los roles nuevos los
> crea el bootstrap, que sólo corre sobre un volumen vacío, y la migración se
> detiene diciéndolo en vez de conceder privilegios a medias.

El script **no borra nada**. Empezar de cero es un gesto aparte:

```bash
docker compose -f infra/local/compose.yaml -p fincilia-local down --volumes
```

Los seis servicios quedan **healthy**: `postgres`, `valkey`, `objectstore`,
`api`, `worker` y `web`. `--wait` no vuelve hasta que cada healthcheck pasa, así
que un `0` significa que el stack sirve, no que los contenedores arrancaron.

Comprobación de un vistazo:

```bash
curl -s http://127.0.0.1:58080/health/ready
```

```json
{"status":"ready","dependencies":[
  {"name":"postgresql","status":"up","detail":"fincilia_app@17.11"},
  {"name":"schema","status":"up","detail":"head V0002"},
  {"name":"valkey","status":"up","detail":"pong"},
  {"name":"object_storage","status":"up","detail":"4 buckets"}]}
```

### Los tres pasos por separado

`up.sh` no hace nada que no puedas hacer a mano, y a veces conviene:

```bash
docker compose -f infra/local/compose.yaml -p fincilia-local up -d --wait postgres valkey objectstore
docker compose -f infra/local/compose.yaml -p fincilia-local --profile migrate run --rm migrate
docker compose -f infra/local/compose.yaml -p fincilia-local up -d --wait
```

```json
{"applied": ["V0001", "V0002"], "head": "V0002", "mutated": true, "ok": true}
```

Repetir la migración devuelve `"mutated": false`. Las migraciones no corren en el
arranque de la API a propósito: un servicio que migra al arrancar migra una vez
por réplica, y convierte un despliegue en un cambio de esquema. Detalle en
[`db/README.md`](../../db/README.md).

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

### Subir un documento

Con la sesión abierta, en la página de una empresa. Sólo si el rol incluye
`document.upload`: Ana puede, Carla no.

Lo que ocurre con los bytes, en orden:

1. **Techo mientras se lee**, no después. Comprobar el tamaño al final es
   comprobarlo cuando el fichero ya está entero en memoria.
2. **El tipo lo deciden los primeros bytes**, nunca la extensión. Un ejecutable
   renombrado a `.csv` se rechaza; un CSV llamado `.txt` entra, y la discrepancia
   queda registrada.
3. **Idempotencia por contenido.** Los mismos bytes en la misma empresa son la
   misma entrega, aunque el fichero se llame distinto. No hace falta que el
   cliente mande una clave de idempotencia que puede equivocarse.
4. **Cuarentena antes que zona de evidencia.** Si aparece una tarjeta que pasa
   Luhn, una clave privada o una credencial, el fichero se conserva en
   `quarantine` y **no** se promueve a `raw` ni se encola para procesar. Se
   conserva en vez de borrarse: borrar la evidencia de un incidente es la peor
   forma de responder a uno.
5. **El artefacto es inmutable.** El rol runtime tiene `INSERT` y `SELECT` sobre
   `source_artifact`, y no `UPDATE` ni `DELETE`.

Un hallazgo dice **qué tipo** y **en qué línea**, jamás el valor: contener un
secreto no puede consistir en copiarlo a un sitio con menos protección.

### Qué pasa con lo que subes

**Todo aterriza en cuarentena.** Sin excepciones por formato. Salir de ahí es una
decisión aparte, que toma un trabajo de escaneo y que queda escrita.

Se promueve a la zona de evidencia lo que se ha podido **inspeccionar de principio
a fin**, y hoy eso es CSV y nada más. Un PDF o un libro de cálculo se quedan en
cuarentena con el motivo `no_scanner_for_format`, y la web lo dice. Prometer que
están soportados sería peor que decir que no lo están.

Un ZIP se identifica por su manifiesto, no por la extensión: `xl/workbook.xml` lo
hace un `xlsx`, la entrada `mimetype` lo hace un `ods`, y un ZIP cualquiera se
queda en ZIP. Un libro con `xl/vbaProject.bin` se rechaza en la puerta: una macro
es código.

Lo que trae una tarjeta que pasa Luhn, una clave privada o una credencial se queda
con `sensitive_content`. El hallazgo dice **qué tipo** y **en qué línea**, jamás el
valor.

Y sólo lo promovido se perfila: perfilar es leer el fichero entero, y eso no se
hace sobre algo que no ha pasado inspección.

> Esto **no resuelve** S-01 ni TM-005. La detección de PAN antes de `raw` sigue
> dependiendo de una decisión humana pendiente, y el fichero sigue aterrizando en
> cuarentena antes de que nadie lo mire.

### Qué hace el worker con lo que subiste

Lo que llega a `raw` se encola para perfilar. El worker toma el trabajo, lee el
fichero y guarda su **forma**: separador, codificación, si trae cabecera, cuántas
filas, y de qué tipo parece cada columna. El resultado aparece en la página del
documento.

El perfil **no lleva ni un valor del fichero**. Cuenta y mide; nunca transcribe.
Si llevara ejemplos, sería una copia parcial del documento viviendo donde vive el
metadato, con otras reglas de acceso y otra vida útil.

Y ante una ambigüedad de dinero o de fecha, **no adivina**. `1.234` puede ser mil
doscientos treinta y cuatro o uno coma doscientos treinta y cuatro; `02/01/2026`
puede ser el 2 de enero o el 1 de febrero. La columna queda marcada como
ambigua y la decisión espera a una persona. Basta con que **una** fila del
fichero sea inequívoca (`15/03/2026`) para resolver la columna entera: un banco
no cambia de formato a mitad de un extracto.

Un trabajo nunca se queda a medias. Si el fichero no se deja leer, si el objeto
no está, o si el resultado no se puede guardar, la ejecución queda `failed` con
un código. Un trabajo colgado en `running` no lo reintenta nadie y no aparece en
ninguna lista.

### De la forma a los valores

Promover encola **dos** lecturas independientes, y son dos porque hacen cosas
opuestas. Perfilar mide sin transcribir; extraer transcribe con coordenadas.
Que una falle no impide la otra.

La extracción guarda cada registro del fichero —membrete y cabecera incluidos—
con su tramo exacto de bytes. Decidir cuáles son datos es del mapeo, y guardar
sólo los que hoy parecen datos obligaría a releer la evidencia en cuanto alguien
moviera la cabecera.

Esos valores **no** salen por la página del documento. Van a `raw_record`, que
exige contexto de empresa, y se leen por un endpoint aparte que pide
`dataset.map`: el perfil dice cómo es el fichero y la vista previa dice qué pone
en él, y son dos permisos distintos.

### Antes de poder publicar: aprobar la versión del motor

Publicar afirma que algo se puede reproducir, y esa afirmación se apoya en una
versión del motor que alguien miró. La semilla la deja en `draft` a propósito:
aprobar es una decisión humana y ni el agente ni el sembrador la toman por ti.

Primero mira qué vas a firmar:

```bash
docker compose -f infra/local/compose.yaml -p fincilia-local --profile migrate run --rm migrate python -m db.admin.releases show --release fnc-p3-mapping-0.1.0
```

Y después fírmalo con tu nombre:

```bash
docker compose -f infra/local/compose.yaml -p fincilia-local --profile migrate run --rm migrate python -m db.admin.releases approve --release fnc-p3-mapping-0.1.0 --actor "tu.nombre" --ref "ACTA-LOCAL" --rationale "entorno sintetico local"
```

Queda escrito quién, cuándo, con qué referencia y sobre qué digest de
componentes. Si alguien cambia los componentes después, la API deja de publicar y
dice por qué: la firma cubría otra cosa.

`datasets --release ...` contesta qué se produjo con una versión, que es lo
primero que hay que saber antes de retirarla con `supersede`.

### Fuentes y cuentas: el orden importa

Un movimiento canónico ocurre siempre contra una cuenta, y un registro de origen
viene siempre de una fuente. En **Fuentes y cuentas** se crean las dos y se
vinculan, y hasta que ese vínculo existe no hay contra qué publicar.

El identificador de la cuenta se pide una vez y **no se guarda**: se convierte en
una huella con clave dedicada y de lo que escribes sólo quedan los cuatro últimos
dígitos. No aparece en la fila, ni en el rastro de auditoría, ni en el mensaje de
un error.

Una fuente se vincula con varias cuentas y con un papel: una pasarela liquida a
una cuenta bancaria y concilia contra un libro contable. Sólo hay una principal
viva a la vez, porque «contra qué cuenta se publica esto» tiene que tener una
sola respuesta.

Y el ciclo esperado dice cada cuánto llega un documento, con cuántos días de
plazo y de gracia. El atraso se calcula al leer, contra la fecha de hoy: guardarlo
exigiría un proceso nocturno, y el día que no corriera nada estaría atrasado.

### Mapear y publicar

En la página del documento hay un enlace, **Mapear y publicar**, con cuatro
vistas: Original, Extracción, Mapping y Canónico.

Se asignan columnas eligiendo de una lista que son las columnas del fichero, con
su cabecera y el tipo inferido. Lo que el perfilador marcó ambiguo sale con un
formulario que nombra lo que se elige —convenio de fecha, convenio decimal— y
**exige el motivo**. El motivo no es burocracia: dentro de un año es lo único que
explica por qué este extracto se leyó dd/mm y el del mes siguiente no.

Preparar deja los movimientos **validados**, no publicados. Publicarlos es de
otra persona: en la demo, Ana prepara y Beto publica. Ana no puede publicar lo
suyo aunque tuviera el permiso, y la interfaz lo dice antes de que lo intente.

Desde cualquier importe publicado se llega a la celda que lo produjo: fila,
columna, tramo de bytes y huella del artefacto, con la transformación escrita.

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
| `worker` | construida de `workers/document/Dockerfile` | — | escanea y perfila; rol propio, sin salida a internet |
| `web` | construida de `apps/web/Dockerfile` | `127.0.0.1:53000` | Next.js; nunca autoriza |

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

# Web: typecheck y lint dentro de su imagen de construccion
docker build --target build -f apps/web/Dockerfile -t fincilia-web-check .
docker run --rm fincilia-web-check npm run lint

# Contrato del stack
python -m tools.local_stack.validate
python -m unittest tools.local_stack.test_validate

# API: dentro de su imagen, que es donde viven sus dependencias
docker compose -f infra/local/compose.yaml -p fincilia-local run --rm --no-deps \
  api python -m unittest discover -s /app/tests -t /app/tests

# Esquema: plan sin base, y aislamiento contra PostgreSQL real
docker compose -f infra/local/compose.yaml -p fincilia-local --profile migrate   run --rm migrate python -m unittest discover -s /app/db/tests -t /app

# Worker: toma de trabajos y perfilado, contra PostgreSQL y MinIO reales
docker compose -f infra/local/compose.yaml -p fincilia-local \
  run --rm --no-deps worker python -m unittest discover -s /app/tests -t /app/tests

# Reconciliar registro y almacen de objetos (no borra nada)
docker compose -f infra/local/compose.yaml -p fincilia-local --profile migrate \
  run --rm migrate python -m db.reconcile.objects --company <id-de-empresa>

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
| un documento en `quarantine` con `no_scanner_for_format` | es correcto: todavía no hay analizador seguro para ese formato |
| un trabajo en `failed` con `attempts_exhausted` | mira `dead_letter_item`: agotó sus intentos y espera a una persona |
| un trabajo en `failed` con `authorization_changed` | los permisos de la empresa cambiaron mientras estaba en cola |
| un documento sin perfil | mira su ejecución: `queued` es que el worker no ha llegado, `failed` trae el motivo |
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
6. La versión del motor con la que se publica nace `draft`. Aprobarla es una
   decisión humana con `approval_ref`, y este entorno no la toma. Para datos
   sintéticos no bloquea; para producción sí.
7. Una publicación admite lo mismo que la extracción: doscientas mil filas.
   Medido en CI con cien mil: **94,2 s** en total —17,1 de extracción y 76,9 de
   preparación en 50 lotes—, con un pico de **195,9 MiB** de memoria residente y
   **49,2 MiB** de crecimiento sobre la línea base del proceso. Un conjunto mayor
   se rechaza diciéndolo.
8. La extracción lee en corriente y escribe por tandas, cada una por `COPY` a una
   tabla temporal que desaparece al confirmar: el proceso nunca sostiene más de
   una tanda. Reanudar tras fallar entre dos no duplica ni una fila, y el
   recuento y el digest son los mismos que los de una lectura entera.
9. **La preparación sigue viviendo en la API**, con presupuesto de tiempo y un
   `202` para que el llamante continúe. Funciona y es honesto, pero un trabajo de
   minutos pertenece a la cola: es el cuello que queda por resolver.
10. La excepción por fila (`lineage_row_override`) se crea y se aprueba por API, y
    el camino de un movimiento la enseña en su posición lógica. **No hay pantalla
    para escribirla.**

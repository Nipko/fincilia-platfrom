# Base de datos

Esquema autoritativo de Fincilia sobre PostgreSQL 17, y el aplicador que lo lleva
de una base vacía al estado que espera la API.

~~~text
db/
├── migrate/apply.py   aplicador: una transacción por migración, lock, checksum
├── migrations/        V####__nombre.sql, banda reservada V0001-V0999
├── seed/local.py      firma y empresas de demo, idempotente y determinista
└── tests/             todo lo que exige PostgreSQL real: plan, aislamiento y
                       el recorrido de autorización de la API
~~~

## Alcance: local, sintético, y nada más

`docs/database/migration-tooling.json` declara `local_build.local_product_build_allowed:
true`. Ese permiso es **solo** para construir y ejecutar el producto en el entorno
local con datos sintéticos, y el propio contrato enumera lo que **no** implica:

- ADR-002 no está aceptado.
- No hay herramienta de migración seleccionada.
- S1 no está aprobado.
- `product_migrations_allowed` sigue en `false`.
- No autoriza desplegar en ningún entorno compartido.

Promover este esquema a un entorno con datos reales sigue exigiendo esas
decisiones humanas, con owner asignado y ADR aceptado.

## Aplicar

Las migraciones **no** corren al arrancar la API: un servicio que migra al
arrancar migra una vez por réplica. Van por perfil, invocadas a mano.

~~~bash
docker compose -f infra/local/compose.yaml -p fincilia-local --profile migrate run --rm migrate
~~~

Salida en JSON con `plan`, `applied`, `already_applied`, `head` y `mutated`.
Repetir el comando devuelve `"mutated": false` sin tocar nada. Para ver el plan
sin base de datos:

~~~bash
python -m db.migrate.apply --plan-only
~~~

## Sembrar

~~~bash
docker compose -f infra/local/compose.yaml -p fincilia-local --profile migrate   run --rm migrate python -m db.seed.local
~~~

Una firma, dos empresas y cuatro usuarios, todo sintético. Los identificadores
salen de `uuid5` sobre un espacio de nombres fijo: resembrar no duplica nada y un
enlace a una empresa sigue funcionando después de recrear el volumen. Se niega a
correr si `FINCILIA_REAL_DATA_ENABLED` está encendido.

Aprovisionar también declara sobre qué empresa actúa: con `FORCE ROW LEVEL
SECURITY` no hay vía privilegiada que se salte la política, ni siquiera para el
propietario del esquema.

## Invariantes que sostiene el aplicador

Salieron del spike `spikes/FNC-DB-002`, ejecutado contra PostgreSQL real, y aquí
son código de producto:

| Invariante | Por qué |
|---|---|
| Una transacción por migración | un fallo a mitad no deja objetos parciales ni fila de historial |
| `pg_advisory_xact_lock` | dos migradores concurrentes producen una sola aplicación; el lock se suelta al terminar, sin limpieza |
| Checksum comprobado antes de ejecutar | editar una migración ya aplicada aborta, en vez de aplicar algo distinto de lo revisado |
| `applied_at` del servidor | el reloj del cliente no decide el orden del historial |
| Forward-only | no hay `down`; un fallo se corrige con una migración nueva |
| Finales de línea normalizados antes del hash | un checkout en Windows no puede producir otro checksum del mismo contenido |

## Lo que el esquema garantiza sobre la evidencia

| Tabla | Invariante | Cómo se sostiene |
|---|---|---|
| `source_artifact` | una entrega es un hecho, no se corrige | `GRANT SELECT, INSERT` y `REVOKE UPDATE, DELETE` para el rol runtime |
| `source_artifact` | los mismos bytes son la misma entrega | `UNIQUE (company_id, content_sha256)` |
| `source_artifact` | lo que está en cuarentena no puede decir que está almacenado | `CHECK` que acopla `zone` y `status` |
| `processing_run` | un trabajo terminado tiene principio y fin, y el fin no precede al principio | `CHECK` sobre la línea temporal |
| `processing_run` | fallar exige decir por qué | `CHECK` que exige `error_code` sólo al fallar |
| `audit_event` | append-only también por privilegio | `GRANT SELECT, INSERT` y nada más |
| `dispatch_pointer` | sólo identificadores y marcas de tiempo | excepción de RLS declarada y con columnas fijadas por el validador |

`ALTER DEFAULT PRIVILEGES` de V0001 concede `UPDATE` a toda tabla nueva del
esquema, así que quitarlo es un acto explícito en cada migración que crea una
tabla append-only. Un privilegio heredado por defecto es justo el que nadie
recuerda revisar.

## La única tabla sin RLS, y por qué

`fincilia.dispatch_pointer` no lleva RLS. Es deliberado y está **declarado** en
`docs/database/migration-tooling.json`, con motivo, dueño y gate.

El problema que resuelve es de arranque en frío: un planificador que trabaja para
varias empresas necesita saber qué empresa tiene trabajo pendiente **antes** de
poder fijar su contexto, y con `FORCE ROW LEVEL SECURITY` leer sin contexto no
devuelve nada. Las alternativas eran dar `BYPASSRLS` al worker —que convierte el
aislamiento en una promesa— o abrir `processing_run` a un contexto especial, que
es lo mismo con otro nombre y además abre la fila entera, porque RLS es por fila
y no por columna.

Lo que se ve por esta vía es «la empresa X tiene un trabajo pendiente». No hay
nombre de fichero, ni tipo, ni tamaño, ni importe, ni sujeto. `tools/migration_readiness`
comprueba que las columnas siguen siendo exactamente las declaradas: añadir aquí
un dato de negocio deja de ser invisible y vuelve a exigir una revisión. Y si la
tabla llegara a tener RLS, la excepción se marca como obsoleta y bloquea.

## Roles

El runtime **no** es propietario, ni superusuario, ni `BYPASSRLS`.

| Rol | Para qué | Qué no puede |
|---|---|---|
| `fincilia_migrator` | crear y modificar el esquema | no atiende tráfico |
| `fincilia_app` | leer y escribir datos | no hace DDL, no reescribe auditoría, no desactiva RLS |

Con `FORCE ROW LEVEL SECURITY` el propietario tampoco queda exento: sin `FORCE`,
el aislamiento se sostiene solo mientras nadie se conecte con el rol equivocado.
Toda tabla con `company_id` lo lleva, y `tools/migration_readiness` lo comprueba
sobre el fichero: una tabla con `company_id` sin RLS forzada es una fuga
silenciosa, porque la consulta correcta devuelve filas de otra empresa y nadie ve
un error.

## Pruebas

~~~bash
# Plan y aislamiento, dentro de la imagen, contra la base levantada
docker compose -f infra/local/compose.yaml -p fincilia-local --profile migrate \
  run --rm migrate python -m unittest discover -s /app/db/tests -t /app

# Contrato del fichero de migraciones, sin levantar nada
python -m unittest tools.migration_readiness.test_validate
~~~

Que una política de RLS funcione es una propiedad del motor, no del código que la
escribe: un doble diría que sí siempre. Por eso las pruebas de aislamiento se
ejecutan contra PostgreSQL real, siembran con el rol migrator y leen con el rol
runtime.

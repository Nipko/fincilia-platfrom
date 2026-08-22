# Base de datos

Esquema autoritativo de Fincilia sobre PostgreSQL 17, y el aplicador que lo lleva
de una base vacía al estado que espera la API.

~~~text
db/
├── migrate/apply.py   aplicador: una transacción por migración, lock, checksum
├── migrations/        V####__nombre.sql, banda reservada V0001-V0999
└── tests/             plan (sin base) y aislamiento (contra PostgreSQL real)
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

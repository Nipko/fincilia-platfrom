# Worker de documentos

Toma trabajos de la cola, lee un fichero que **ya** salió de cuarentena, calcula
su forma y guarda el perfil.

## Lo que no hace

No publica movimientos, no concilia, no cierra nada y no decide nada financiero.
Su salida es metadato: cuántas filas, qué separador, de qué tipo parece cada
columna. Nunca un importe ni un asiento.

Tampoco tiene salida a internet: en `infra/local/compose.yaml` está sólo en la
red `internal`. Procesa ficheros que vienen de fuera, y darle salida sería darle
salida a lo que esos ficheros consigan que ejecute.

## Cómo toma trabajo

Dos pasos, en este orden, y cada uno hace una cosa:

1. `dispatch_pointer` dice **qué empresa** tiene trabajo pendiente. Es lo mínimo
   que un planificador entre empresas necesita antes de poder fijar su contexto
   de RLS, y por eso esa tabla no lleva nada más que identificadores.
2. Con el contexto ya fijado, `processing_run` —que sí tiene RLS— decide de
   verdad si el trabajo se ejecuta, con `FOR UPDATE SKIP LOCKED`. Dos workers
   compitiendo por la misma fila no la ejecutan dos veces: el segundo la salta.

Si el proceso muere entre los dos pasos, el puntero queda reclamado y el trabajo
en `queued`. Pasados cinco minutos vuelve al reparto. Perder un trabajo en
silencio sería peor que ejecutarlo dos veces, y ejecutarlo dos veces tampoco
rompe nada porque el perfilado es idempotente sobre el mismo artefacto.

## Salud

El worker no expone HTTP: darle un puerto sólo para el healthcheck sería
superficie sin uso. Publica un fichero con `mtime` fresco en `/tmp`, que
distingue «vivo» de «colgado».

Antes de trabajar espera a que respondan PostgreSQL, el **esquema**, Valkey y el
almacén de objetos. Si no lo hacen en 30 s, **sale con 1**: no se declara sano un
proceso que no puede trabajar. Contra una base sin migrar eso significa que el
worker no arranca, y es lo correcto — por eso `infra/local/up.sh` migra antes de
levantar las aplicaciones.

## Pruebas

~~~bash
docker compose -f infra/local/compose.yaml -p fincilia-local \
  run --rm --no-deps worker python -m unittest discover -s /app/tests -t /app/tests
~~~

Corren contra PostgreSQL y MinIO reales, porque lo que prueban es el
comportamiento del motor: que `SKIP LOCKED` impida ejecutar dos veces, que RLS
siga acotando lo que el worker ve, y que un puntero de un proceso muerto vuelva
al reparto. Escriben en las empresas `Banco de Pruebas`, sobre las que nadie
tiene concesión: lo que dejan ahí no lo ve ningún usuario.

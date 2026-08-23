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

El worker **no escribe la cola**. Su rol no tiene `UPDATE` sobre `processing_run`
ni privilegio alguno sobre `dispatch_pointer`: lo que tiene es permiso para
ejecutar dos funciones con parámetros validados.

`claim_next_run` se llama sin contexto de empresa. Lee el puntero —lo único
legible sin contexto, y sólo lleva identificadores y marcas de tiempo—, fija el
contexto de esa empresa, y bajo RLS reclama el trabajo con un arriendo y un
testigo. Al salir **restaura** el contexto: `Database.session()` lo fija una vez
al abrir la transacción y no lo vuelve a mirar, así que un contexto filtrado
reetiquetaría en silencio lo que viniera después.

`finish_run` sólo cierra un trabajo si se le presenta el testigo vigente. Un
worker que revive después de que otro recuperó el trabajo recibe `stale_lease` y
no escribe nada: ni resultado, ni estado, ni puntero.

Tres invariantes, y cada uno existe por un fallo que se pudo reproducir:

- **Terminal y sin puntero son un solo hecho**, en la misma transacción. La
  versión anterior borraba el puntero desde fuera, sin comprobar nada, y podía
  dejar un trabajo en `running` sin puntero: invisible para siempre.
- **El arriendo tiene testigo.** Sin él no se distingue a quien está trabajando de
  quien **estuvo** trabajando.
- **El worker no libera nada por su cuenta.** La recuperación de un arriendo
  vencido la hace el propio reclamo, que ve las dos filas a la vez.

Un trabajo que agota sus intentos no vuelve a la cola: acaba en
`dead_letter_item`, visible y minimizado. Y lo que no se supo clasificar no se
reintenta a ciegas: `unknown` va a carta muerta marcada `requires_human`.

## Dos clases de trabajo

`scan` lee de cuarentena y decide si algo puede salir. `profile` lee de la zona de
evidencia y calcula la forma del fichero. **Nada se perfila desde cuarentena**: si
se pudiera, la regla de inspección previa no serviría de nada.

Sólo se promueve lo que se inspecciona de principio a fin. Hoy eso es CSV; un PDF
o un libro de cálculo se quedan donde están, con el motivo escrito.

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

Aquí sólo vive la clasificación de fallos, que es lógica pura: de ella depende si
un trabajo se reintenta, muere, o acaba delante de una persona.

El protocolo —arriendos, recuperación, reintentos y carta muerta— se prueba contra
PostgreSQL real y **con las credenciales de cada rol** en
`db/tests/test_dispatch_protocol.py`. Ahí es donde tiene sentido: son propiedades
del motor y de los privilegios, no del código que las invoca. Afirmar un
privilegio negativo desde otro rol no prueba nada.

# Sonda de semántica de PostgreSQL para FNC-P2.1

Seis preguntas de las que depende el diseño del despachador, y ninguna se
contesta con seguridad suficiente leyendo documentación. Se contestan contra el
motor.

```bash
docker compose -f infra/local/compose.yaml -p fincilia-local exec -T -u postgres \
  postgres psql -v ON_ERROR_STOP=1 -U fincilia_migrator -d fincilia_local \
  -f - < spikes/FNC-P2.1/probe_definer_rls.sql
```

Ejecutada contra PostgreSQL 17.11, con el rol `fincilia_migrator`, que es el
propietario del esquema y **no** es superusuario. Resultados:

| # | Pregunta | Respuesta | Consecuencia en el diseño |
|---|---|---|---|
| 1 | ¿Una función `SECURITY DEFINER` cuyo dueño es el dueño de la tabla se salta `FORCE ROW LEVEL SECURITY`? | **No.** Devolvió `0` filas sin contexto. | La función de reclamo **tiene** que fijar el contexto de empresa ella misma. `SECURITY DEFINER` reduce privilegios de tabla, no aislamiento. |
| 2 | ¿Puede un rol no superusuario declarar `SET "fincilia.company_id"` como cláusula de función, para que se restaure sola al salir? | **No.** `permission denied to set parameter`. | Descartada la restauración automática. |
| 3 | ¿Basta con guardar y restaurar el contexto a mano dentro de la función? | **Sí.** Tras la llamada, el contexto del llamante quedó vacío y volvió a ver `0` filas. | La función guarda `current_setting(..., true)` al entrar y lo restaura antes de salir. |
| 4 | ¿Funciona `FOR UPDATE SKIP LOCKED` dentro de un CTE que alimenta un `UPDATE`? | **Sí.** | El reclamo es una sola sentencia: sin ventana entre elegir y marcar. |
| 5 | ¿Puede un rol sin `UPDATE` escribir a través de una función `SECURITY DEFINER`? | **Sí.** `has_table_privilege(...,'UPDATE') = false` y `has_function_privilege(..., 'EXECUTE') = true`. | La API puede encolar sin tener ni un privilegio sobre `dispatch_pointer`. |
| 6 | ¿Una FK compuesta puede apuntar a `(PK, otra columna)`? | Sólo con un `UNIQUE` en el destino: sin él, *«there is no unique constraint matching given keys»*. Con él, un puntero cruzado se rechaza con `foreign_key_violation`. | `processing_run` gana `UNIQUE (run_id, company_id)` y `dispatch_pointer` referencia esa pareja. |

## Por qué esto vale la pena

El punto 1 es el que decide el diseño entero. La intuición razonable —«una
función `SECURITY DEFINER` corre como el dueño, y el dueño ve todo»— es **falsa**
cuando la tabla tiene `FORCE ROW LEVEL SECURITY`, que es justamente el caso aquí.
Haberlo asumido habría producido una función de reclamo que no devuelve nada y un
worker que nunca encuentra trabajo, con un síntoma que no señala a la causa.

El punto 2 corrigió la primera versión del diseño, que se apoyaba en una cláusula
`SET` a nivel de función para restaurar el contexto sin esfuerzo.

Esta sonda no forma parte del producto y no se ejecuta en CI: es la evidencia de
por qué el diseño es como es. El comportamiento que fija está cubierto, ya como
código de producto, por las pruebas de `db/tests/` y `workers/document/tests/`.

-- V0006: el reconciliador puede reparar por la misma puerta que la API.
--
-- Reconciliar es una tarea de operacion: compara lo que dice el registro con lo
-- que hay en el almacen de objetos, y lo unico que repara -- si se lo piden -- es
-- reencolar el trabajo de un artefacto que quedo registrado sin cola. Ese residuo
-- lo deja una caida entre escribir la fila y encolar el trabajo.
--
-- Podria insertar en la cola directamente, porque corre con el rol propietario.
-- No lo hace: encolar tiene invariantes -- alcance verificado, artefacto visible
-- bajo la politica, version de autorizacion vigente, trabajo y puntero en la
-- misma transaccion -- y tenerlas escritas dos veces es tenerlas escritas mal una
-- de las dos. Se le concede EXECUTE sobre la misma funcion y se acabo.
--
-- No amplia nada de forma significativa: el migrador ya es el propietario del
-- esquema y puede cambiarlo entero. Lo que se evita es una segunda copia de la
-- logica de encolado viviendo en un script de operacion.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

-- Se concede desde el dueno de la funcion. Un GRANT de quien no es dueno no
-- falla: avisa y no hace nada, que es como las cuatro funciones de V0005
-- quedaron abiertas a PUBLIC en su primera version.
SET LOCAL ROLE fincilia_dispatch;
GRANT EXECUTE ON FUNCTION fincilia.enqueue_processing_run(uuid, uuid, text)
  TO fincilia_migrator;
RESET ROLE;

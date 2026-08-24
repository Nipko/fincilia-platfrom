-- --------------------------------------------------------------------------- --
-- V0013 — Vallado de cada lote por el arriendo vigente (FNC-P3.6-R2)
--
-- `finish_run` ya rechazaba al worker que habia perdido su arriendo, pero para
-- entonces ese worker podia haber escrito otra tanda de `raw_record`. Comprobar
-- el token desde la aplicacion no basta: entre comprobarlo y escribir, otro
-- worker podria recuperar el run.
--
-- Esta funcion toma un bloqueo de fila dentro de la **misma transaccion** que
-- escribe la tanda. `fincilia_worker` no recibe UPDATE sobre la cola; ejerce la
-- operacion minima a traves del rol definer existente. El recuperador espera al
-- commit del lote y, desde que obtiene el nuevo token, el worker anterior ya no
-- puede sostener otro bloqueo.
-- --------------------------------------------------------------------------- --

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

CREATE FUNCTION fincilia.hold_processing_lease(
  p_run_id uuid,
  p_lease_token uuid
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $hold_lease$
BEGIN
  IF p_run_id IS NULL OR p_lease_token IS NULL THEN
    RETURN false;
  END IF;

  PERFORM 1
    FROM fincilia.processing_run r
   WHERE r.run_id = p_run_id
     -- La empresa viene del contexto fijado server-side por Database.session.
     -- Comparar como texto hace que contexto ausente o vacio no lance: niega.
     AND r.company_id::text = current_setting('fincilia.company_id', true)
     AND r.status = 'running'
     AND r.lease_token = p_lease_token
     AND r.lease_expires_at > clock_timestamp()
   FOR NO KEY UPDATE;

  RETURN FOUND;
END;
$hold_lease$;

COMMENT ON FUNCTION fincilia.hold_processing_lease(uuid, uuid) IS
  'Sostiene el arriendo vigente hasta el final de la transaccion del lote; '
  'niega tokens vencidos, reemplazados o de otra empresa.';

-- Una funcion nueva pertenece inicialmente al migrador. Igual que en V0005,
-- se cede al rol sin login y sin DDL que posee el protocolo de despacho.
GRANT CREATE ON SCHEMA fincilia TO fincilia_dispatch;
ALTER FUNCTION fincilia.hold_processing_lease(uuid, uuid)
  OWNER TO fincilia_dispatch;
REVOKE CREATE ON SCHEMA fincilia FROM fincilia_dispatch;

SET LOCAL ROLE fincilia_dispatch;
REVOKE ALL PRIVILEGES ON FUNCTION fincilia.hold_processing_lease(uuid, uuid)
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.hold_processing_lease(uuid, uuid)
  TO fincilia_worker;
RESET ROLE;

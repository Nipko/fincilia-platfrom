-- El historial no duplica filas al repetir la aplicacion.
\set ON_ERROR_STOP on
DO $history$
DECLARE
  total integer;
  distinct_versions integer;
BEGIN
  SELECT count(*), count(DISTINCT version) INTO total, distinct_versions
  FROM spike.schema_history;
  IF total <> distinct_versions THEN
    RAISE EXCEPTION 'FNC_SPIKE_REPLAY history has % rows for % versions',
      total, distinct_versions;
  END IF;
  IF total <> 3 THEN
    RAISE EXCEPTION 'FNC_SPIKE_REPLAY expected 3 history rows, found %', total;
  END IF;
  RAISE NOTICE 'FNC_SPIKE_OK history_count %', total;
END
$history$;

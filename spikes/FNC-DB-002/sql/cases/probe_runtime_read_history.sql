-- El runtime SI puede leer el historial: la denegacion es de escritura, no de lectura.
\set ON_ERROR_STOP on
DO $read_history$
DECLARE applied integer;
BEGIN
  SELECT count(*) INTO applied FROM spike.schema_history;
  IF applied < 1 THEN
    RAISE EXCEPTION 'FNC_SPIKE_HISTORY runtime cannot read the migration history';
  END IF;
  RAISE NOTICE 'FNC_SPIKE_OK runtime_reads_history %', applied;
END
$read_history$;

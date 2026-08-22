-- Estado esperado en head: tabla, indice, columna expand y tres migraciones.
\set ON_ERROR_STOP on
DO $head$
DECLARE
  applied integer;
  has_index boolean;
  has_column boolean;
BEGIN
  SELECT count(*) INTO applied FROM spike.schema_history WHERE status = 'applied';
  IF applied <> 3 THEN
    RAISE EXCEPTION 'FNC_SPIKE_HEAD expected 3 applied migrations, found %', applied;
  END IF;

  SELECT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname = 'spike' AND indexname = 'idx_company_ledger_company_date'
  ) INTO has_index;
  IF NOT has_index THEN
    RAISE EXCEPTION 'FNC_SPIKE_HEAD the V0002 index is missing';
  END IF;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'spike' AND table_name = 'company_ledger'
      AND column_name = 'external_reference' AND is_nullable = 'YES'
  ) INTO has_column;
  IF NOT has_column THEN
    RAISE EXCEPTION 'FNC_SPIKE_HEAD the V0003 expand column is missing or not nullable';
  END IF;

  IF EXISTS (SELECT 1 FROM spike.schema_history WHERE applied_at IS NULL) THEN
    RAISE EXCEPTION 'FNC_SPIKE_HEAD a history row has no server timestamp';
  END IF;

  RAISE NOTICE 'FNC_SPIKE_OK head_state %', applied;
END
$head$;

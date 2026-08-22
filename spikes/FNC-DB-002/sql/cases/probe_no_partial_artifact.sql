-- Tras la migracion que falla no puede quedar ni el objeto ni la fila de historial.
\set ON_ERROR_STOP on
DO $no_partial$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'spike' AND table_name = 'partial_artifact'
  ) THEN
    RAISE EXCEPTION 'FNC_SPIKE_ATOMICITY partial_artifact survived a failed migration';
  END IF;

  IF EXISTS (SELECT 1 FROM spike.schema_history WHERE version = 'V0009') THEN
    RAISE EXCEPTION 'FNC_SPIKE_ATOMICITY a failed migration was recorded as applied';
  END IF;

  RAISE NOTICE 'FNC_SPIKE_OK no_partial_artifact';
END
$no_partial$;

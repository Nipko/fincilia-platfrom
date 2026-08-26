\set ON_ERROR_STOP on
DO $probe$
BEGIN
  IF (SELECT count(*) FROM fnc_lab.work_execution) <> 1 THEN
    RAISE EXCEPTION 'expected exactly one execution claim';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM fnc_lab.work_item
     WHERE work_id = 'synthetic-work-001' AND state = 'running'
       AND fencing_counter = 1 AND lease_token = 1
  ) THEN RAISE EXCEPTION 'claim state is not fenced'; END IF;
END;
$probe$;
SELECT 'FNC_IDEM_001_OK';

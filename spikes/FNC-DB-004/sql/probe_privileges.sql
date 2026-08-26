\set ON_ERROR_STOP on
DO $probe$
BEGIN
  IF has_schema_privilege('fnc_concurrency_runtime', 'fnc_lab', 'CREATE') THEN
    RAISE EXCEPTION 'runtime can create in schema';
  END IF;
  IF has_table_privilege('fnc_concurrency_runtime', 'fnc_lab.work_item', 'INSERT') OR
     has_table_privilege('fnc_concurrency_runtime', 'fnc_lab.work_item', 'UPDATE') OR
     has_table_privilege('fnc_concurrency_runtime', 'fnc_lab.outbox_event', 'DELETE') THEN
    RAISE EXCEPTION 'runtime has direct table writes';
  END IF;
  IF NOT has_function_privilege(
    'fnc_concurrency_runtime', 'fnc_lab.claim_work(text,integer)', 'EXECUTE') THEN
    RAISE EXCEPTION 'runtime cannot execute claim function';
  END IF;
END;
$probe$;
SELECT 'FNC_PRIVILEGES_OK';

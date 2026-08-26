\set ON_ERROR_STOP on
DO $probe$
BEGIN
  IF EXISTS (SELECT 1 FROM fnc_lab.domain_effect) OR
     EXISTS (SELECT 1 FROM fnc_lab.outbox_event) THEN
    RAISE EXCEPTION 'partial domain or outbox state survived rollback';
  END IF;
END;
$probe$;
SELECT 'FNC_ATOMIC_ROLLBACK_OK';

\set ON_ERROR_STOP on
DO $probe$
BEGIN
  IF (SELECT count(*) FROM fnc_lab.domain_effect
       WHERE fencing_token = 2 AND effect_value = 'current-effect') <> 1 THEN
    RAISE EXCEPTION 'current lease did not own the only effect';
  END IF;
  IF EXISTS (SELECT 1 FROM fnc_lab.domain_effect WHERE effect_value = 'stale-effect') THEN
    RAISE EXCEPTION 'stale worker wrote an effect';
  END IF;
  IF (SELECT count(*) FROM fnc_lab.outbox_event WHERE fencing_token = 2) <> 1 THEN
    RAISE EXCEPTION 'outbox does not carry current fencing token';
  END IF;
END;
$probe$;
SELECT 'FNC_IDEM_005_OK';

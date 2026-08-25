\set ON_ERROR_STOP on
DO $probe$
BEGIN
  IF (SELECT count(*) FROM fnc_lab.domain_effect) <> 1 OR
     (SELECT count(*) FROM fnc_lab.outbox_event WHERE state = 'delivered') <> 1 OR
     (SELECT count(*) FROM fnc_lab.delivery_receipt) <> 1 THEN
    RAISE EXCEPTION 'committed effect was not delivered exactly once in the ledger';
  END IF;
  IF (SELECT delivery_attempts FROM fnc_lab.outbox_event) <> 1 THEN
    RAISE EXCEPTION 'unexpected delivery attempt count';
  END IF;
END;
$probe$;
SELECT 'FNC_IDEM_004_OK';

\set ON_ERROR_STOP on
DO $probe$
BEGIN
  IF (SELECT count(*) FROM fnc_lab.domain_effect) <> 1 OR
     (SELECT count(*) FROM fnc_lab.outbox_event WHERE state = 'pending') <> 1 OR
     EXISTS (SELECT 1 FROM fnc_lab.delivery_receipt) THEN
    RAISE EXCEPTION 'crash window did not preserve one pending outbox event';
  END IF;
END;
$probe$;
SELECT 'FNC_OUTBOX_PENDING_OK';

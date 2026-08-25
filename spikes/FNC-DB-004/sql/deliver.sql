\set ON_ERROR_STOP on
\pset tuples_only on
WITH claimed AS (
  SELECT * FROM fnc_lab.claim_outbox(:'dispatcher')
)
SELECT fnc_lab.ack_outbox(claimed.event_id, :'dispatcher') FROM claimed;

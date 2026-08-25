\set ON_ERROR_STOP on
\pset tuples_only on
SELECT COALESCE((
  SELECT 'CLAIMED|' || work_id || '|' || fencing_token::text
  FROM fnc_lab.claim_work(:'worker', :'lease_ms'::integer)
), 'NO_CLAIM');

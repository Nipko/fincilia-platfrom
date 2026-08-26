\set ON_ERROR_STOP on
\pset tuples_only on
WITH claimed AS (
  SELECT * FROM fnc_lab.claim_work(:'worker', 60000)
)
SELECT fnc_lab.commit_effect(
  :'worker', claimed.work_id, claimed.fencing_token, 'synthetic-effect', false
) FROM claimed;

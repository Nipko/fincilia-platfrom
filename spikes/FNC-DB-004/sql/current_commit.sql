\set ON_ERROR_STOP on
\pset tuples_only on
SELECT fnc_lab.commit_effect(
  :'worker', 'synthetic-work-001', :'token'::bigint, 'current-effect', false
);

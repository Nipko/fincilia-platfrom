\set ON_ERROR_STOP on
UPDATE fnc_lab.work_item
   SET lease_expires_at = clock_timestamp() - interval '1 second'
 WHERE work_id = 'synthetic-work-001' AND state = 'running';

\set ON_ERROR_STOP on
TRUNCATE fnc_lab.delivery_receipt, fnc_lab.outbox_event, fnc_lab.domain_effect,
  fnc_lab.work_execution, fnc_lab.work_item RESTART IDENTITY CASCADE;
INSERT INTO fnc_lab.work_item(work_id, state) VALUES ('synthetic-work-001', 'queued');

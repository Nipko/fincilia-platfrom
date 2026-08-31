-- FNC-CLS-006: cierre y reapertura append-only de periodos contables.
--
-- El cierre fija evidencia digest-only ya revisada. No crea asientos, no muta
-- movimientos y no certifica estados financieros. Las guardas de esta
-- migracion impiden que una etiqueta de UI sea la unica proteccion del periodo.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

CREATE TABLE fincilia.accounting_period_close (
  close_id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id               uuid NOT NULL REFERENCES fincilia.company(company_id),
  period_start             date NOT NULL,
  period_end               date NOT NULL,
  version                  integer NOT NULL CHECK (version >= 1),
  packet_id                uuid NOT NULL,
  observed_manifest_digest char(64) NOT NULL CHECK (
                             observed_manifest_digest ~ '^[0-9a-f]{64}$'),
  snapshot_schema_version  text NOT NULL CHECK (
                             snapshot_schema_version = 'accounting-close-v1'),
  snapshot                 jsonb NOT NULL,
  snapshot_digest          char(64) NOT NULL CHECK (
                             snapshot_digest ~ '^[0-9a-f]{64}$'),
  closed_by                uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  closed_at                timestamptz NOT NULL DEFAULT now(),
  audit_event_id           uuid NOT NULL,

  CONSTRAINT uq_accounting_period_close_company UNIQUE (close_id, company_id),
  CONSTRAINT uq_accounting_period_close_version UNIQUE
    (company_id, period_start, period_end, version),
  CONSTRAINT uq_accounting_period_close_packet UNIQUE (packet_id),
  CONSTRAINT fk_accounting_period_close_packet FOREIGN KEY (packet_id, company_id)
    REFERENCES fincilia.close_review_packet(packet_id, company_id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_accounting_period_close_audit FOREIGN KEY (audit_event_id, company_id)
    REFERENCES fincilia.audit_event(audit_event_id, company_id)
    ON DELETE RESTRICT,
  CONSTRAINT ck_accounting_period_close_window CHECK (period_end >= period_start),
  CONSTRAINT ck_accounting_period_close_snapshot_size CHECK (
    pg_column_size(snapshot) <= 1048576)
);

CREATE TABLE fincilia.accounting_period_reopen_request (
  request_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id       uuid NOT NULL REFERENCES fincilia.company(company_id),
  close_id         uuid NOT NULL,
  reason_code      text NOT NULL CHECK (reason_code IN (
                     'late_evidence', 'material_error', 'regulatory_adjustment',
                     'scope_correction', 'other_documented')),
  rationale        text NOT NULL CHECK (length(rationale) BETWEEN 10 AND 500),
  requested_by     uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  requested_at     timestamptz NOT NULL DEFAULT now(),
  audit_event_id   uuid NOT NULL,

  CONSTRAINT uq_period_reopen_request_company UNIQUE (request_id, company_id),
  CONSTRAINT uq_period_reopen_request_close UNIQUE (close_id),
  CONSTRAINT fk_period_reopen_request_close FOREIGN KEY (close_id, company_id)
    REFERENCES fincilia.accounting_period_close(close_id, company_id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_period_reopen_request_audit FOREIGN KEY (audit_event_id, company_id)
    REFERENCES fincilia.audit_event(audit_event_id, company_id)
    ON DELETE RESTRICT
);

CREATE TABLE fincilia.accounting_period_reopen_decision (
  decision_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id     uuid NOT NULL REFERENCES fincilia.company(company_id),
  request_id     uuid NOT NULL,
  decision       text NOT NULL CHECK (decision IN ('approved', 'rejected')),
  reason_code    text NOT NULL CHECK (reason_code IN (
                   'documented_basis_confirmed', 'insufficient_basis',
                   'wrong_scope', 'duplicate_request')),
  decided_by     uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  decided_at     timestamptz NOT NULL DEFAULT now(),
  audit_event_id uuid NOT NULL,

  CONSTRAINT uq_period_reopen_decision_company UNIQUE (decision_id, company_id),
  CONSTRAINT uq_period_reopen_decision_terminal UNIQUE (request_id),
  CONSTRAINT fk_period_reopen_decision_request FOREIGN KEY (request_id, company_id)
    REFERENCES fincilia.accounting_period_reopen_request(request_id, company_id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_period_reopen_decision_audit FOREIGN KEY (audit_event_id, company_id)
    REFERENCES fincilia.audit_event(audit_event_id, company_id)
    ON DELETE RESTRICT
);

CREATE TABLE fincilia.accounting_period_command_receipt (
  receipt_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id      uuid NOT NULL REFERENCES fincilia.company(company_id),
  actor_id        uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  action          text NOT NULL CHECK (action IN (
                    'close', 'request_reopen', 'approve_reopen', 'reject_reopen')),
  idempotency_key text NOT NULL CHECK (
                    length(idempotency_key) BETWEEN 16 AND 128
                    AND idempotency_key ~ '^[A-Za-z0-9._:-]+$'),
  request_digest  char(64) NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
  result_kind     text NOT NULL CHECK (result_kind IN (
                    'close', 'reopen_request', 'reopen_decision')),
  result_ref      uuid NOT NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_period_command_receipt_company UNIQUE (receipt_id, company_id),
  CONSTRAINT uq_period_command_receipt_key UNIQUE
    (company_id, actor_id, idempotency_key)
);

CREATE INDEX idx_accounting_period_close_period ON fincilia.accounting_period_close
  (company_id, period_end DESC, period_start DESC, version DESC, close_id);
CREATE INDEX idx_period_reopen_request_time ON fincilia.accounting_period_reopen_request
  (company_id, requested_at DESC, request_id);
CREATE INDEX idx_period_reopen_decision_time ON fincilia.accounting_period_reopen_decision
  (company_id, decided_at DESC, decision_id);

CREATE FUNCTION fincilia.accounting_period_is_closed(
  requested_company_id uuid, requested_start date, requested_end date
) RETURNS boolean
LANGUAGE sql
STABLE
SET search_path = pg_catalog, fincilia
AS $function$
  SELECT EXISTS (
    SELECT 1
    FROM fincilia.accounting_period_close c
    WHERE c.company_id = requested_company_id
      AND daterange(c.period_start, c.period_end, '[]')
          && daterange(requested_start, requested_end, '[]')
      AND NOT EXISTS (
        SELECT 1
        FROM fincilia.accounting_period_reopen_request r
        JOIN fincilia.accounting_period_reopen_decision d
          ON d.request_id = r.request_id AND d.company_id = r.company_id
        WHERE r.close_id = c.close_id
          AND r.company_id = c.company_id
          AND d.decision = 'approved'
      )
  )
$function$;

REVOKE ALL ON FUNCTION fincilia.accounting_period_is_closed(uuid, date, date)
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.accounting_period_is_closed(uuid, date, date)
  TO fincilia_app, fincilia_migrator;

CREATE FUNCTION fincilia.validate_accounting_period_close()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  packet fincilia.close_review_packet%ROWTYPE;
  reviewed_by uuid;
  next_version integer;
  item jsonb;
BEGIN
  PERFORM pg_advisory_xact_lock(hashtextextended(NEW.company_id::text, 35006));

  SELECT * INTO packet
  FROM fincilia.close_review_packet
  WHERE packet_id = NEW.packet_id AND company_id = NEW.company_id;

  SELECT d.decided_by INTO reviewed_by
  FROM fincilia.close_review_decision d
  WHERE d.packet_id = NEW.packet_id
    AND d.company_id = NEW.company_id
    AND d.decision = 'evidence_reviewed'
    AND d.observed_manifest_digest = NEW.observed_manifest_digest;

  IF packet.packet_id IS NULL
     OR packet.period_start <> NEW.period_start
     OR packet.period_end <> NEW.period_end
     OR packet.manifest_digest <> NEW.observed_manifest_digest
     OR reviewed_by IS NULL
     OR reviewed_by <> NEW.closed_by
     OR packet.prepared_by = NEW.closed_by THEN
    RAISE EXCEPTION 'period close requires the assigned reviewed packet'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_period_close_reviewed_packet';
  END IF;

  IF EXISTS (
    SELECT 1 FROM fincilia.close_review_packet newer
    WHERE newer.company_id = NEW.company_id
      AND newer.period_start = NEW.period_start
      AND newer.period_end = NEW.period_end
      AND newer.version > packet.version
  ) THEN
    RAISE EXCEPTION 'a newer close review packet exists'
      USING ERRCODE = '40001', CONSTRAINT = 'ck_period_close_latest_packet';
  END IF;

  IF fincilia.accounting_period_is_closed(
      NEW.company_id, NEW.period_start, NEW.period_end) THEN
    RAISE EXCEPTION 'accounting period already closed or overlaps an active close'
      USING ERRCODE = '23P01', CONSTRAINT = 'ck_period_close_no_overlap';
  END IF;

  SELECT COALESCE(max(version), 0) + 1 INTO next_version
  FROM fincilia.accounting_period_close
  WHERE company_id = NEW.company_id
    AND period_start = NEW.period_start
    AND period_end = NEW.period_end;
  IF NEW.version <> next_version THEN
    RAISE EXCEPTION 'accounting period close version is not next'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_period_close_version';
  END IF;

  IF jsonb_typeof(NEW.snapshot) <> 'object'
     OR (SELECT count(*) FROM jsonb_object_keys(NEW.snapshot)) <> 7
     OR NOT NEW.snapshot ?& ARRAY[
       'schema_version', 'packet_id', 'packet_version', 'manifest_digest',
       'controls', 'sources', 'accounts']
     OR NEW.snapshot->>'schema_version' <> NEW.snapshot_schema_version
     OR NEW.snapshot->>'packet_id' <> NEW.packet_id::text
     OR (NEW.snapshot->>'packet_version')::integer <> packet.version
     OR NEW.snapshot->>'manifest_digest' <> NEW.observed_manifest_digest
     OR jsonb_typeof(NEW.snapshot->'controls') <> 'array'
     OR jsonb_typeof(NEW.snapshot->'sources') <> 'array'
     OR jsonb_typeof(NEW.snapshot->'accounts') <> 'array'
     OR jsonb_array_length(NEW.snapshot->'controls') <> 16
     OR jsonb_array_length(NEW.snapshot->'sources') = 0
     OR jsonb_array_length(NEW.snapshot->'accounts') = 0 THEN
    RAISE EXCEPTION 'accounting close snapshot envelope is invalid'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_period_close_snapshot';
  END IF;

  IF (SELECT array_agg(value->>'code' ORDER BY value->>'code')
      FROM jsonb_array_elements(NEW.snapshot->'controls')) <>
     ARRAY[
       'account_balances', 'accounting_dates', 'complete_lineage',
       'completeness_assessments', 'dataset_evidence', 'expectations_satisfied',
       'expected_sources', 'pending_corrections', 'product_close',
       'published_datasets', 'quality_alerts', 'reconciliation_reviews',
       'reconciliation_statement_lineage', 'reconciliation_statements',
       'rejected_rows', 'verified_completeness'] THEN
    RAISE EXCEPTION 'accounting close control set is incomplete'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_period_close_control_set';
  END IF;

  FOR item IN SELECT value FROM jsonb_array_elements(NEW.snapshot->'controls')
  LOOP
    IF (item->>'code' = 'product_close' AND item->>'state' <> 'unavailable')
       OR (item->>'code' <> 'product_close' AND item->>'state' <> 'pass') THEN
      RAISE EXCEPTION 'accounting close contains a blocking control'
        USING ERRCODE = '23514', CONSTRAINT = 'ck_period_close_controls_pass';
    END IF;
  END LOOP;

  FOR item IN SELECT value FROM jsonb_array_elements(NEW.snapshot->'sources')
  LOOP
    IF item->>'expectation_state' <> 'satisfied'
       OR item->>'dataset_state' <> 'published'
       OR item->>'completeness_state' <> 'verified'
       OR item->>'lineage_state' <> 'complete'
       OR (item->>'rejected_count')::integer <> 0 THEN
      RAISE EXCEPTION 'accounting close source is not eligible'
        USING ERRCODE = '23514', CONSTRAINT = 'ck_period_close_source_eligible';
    END IF;
  END LOOP;

  FOR item IN SELECT value FROM jsonb_array_elements(NEW.snapshot->'accounts')
  LOOP
    IF jsonb_typeof(item) <> 'object'
       OR NOT item ?& ARRAY['financial_account_id', 'statement_id',
                            'statement_version', 'statement_state',
                            'statement_lineage_state', 'coverage_state'] THEN
      RAISE EXCEPTION 'accounting close account reference is invalid'
        USING ERRCODE = '23514', CONSTRAINT = 'ck_period_close_account_ref';
    END IF;
    IF (item->>'statement_id') IS NULL
       OR (item->>'statement_version') IS NULL
       OR item->>'statement_state' <> 'balanced'
       OR item->>'statement_lineage_state' <> 'complete'
       OR item->>'coverage_state' <> 'covered' THEN
      RAISE EXCEPTION 'accounting close account is not reconciled'
        USING ERRCODE = '23514', CONSTRAINT = 'ck_period_close_account_eligible';
    END IF;
  END LOOP;
  RETURN NEW;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.validate_accounting_period_close() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.validate_accounting_period_close()
  TO fincilia_app, fincilia_migrator;
CREATE TRIGGER accounting_period_close_guard
  BEFORE INSERT ON fincilia.accounting_period_close
  FOR EACH ROW EXECUTE FUNCTION fincilia.validate_accounting_period_close();

CREATE FUNCTION fincilia.validate_accounting_period_reopen_request()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  source_close fincilia.accounting_period_close%ROWTYPE;
BEGIN
  PERFORM pg_advisory_xact_lock(hashtextextended(NEW.company_id::text, 35006));
  SELECT * INTO source_close FROM fincilia.accounting_period_close
  WHERE close_id = NEW.close_id AND company_id = NEW.company_id;
  IF source_close.close_id IS NULL OR NOT fincilia.accounting_period_is_closed(
      NEW.company_id, source_close.period_start, source_close.period_end) THEN
    RAISE EXCEPTION 'only an active close can be reopened'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_period_reopen_active_close';
  END IF;
  RETURN NEW;
END
$function$;

CREATE FUNCTION fincilia.validate_accounting_period_reopen_decision()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  source_request fincilia.accounting_period_reopen_request%ROWTYPE;
BEGIN
  PERFORM pg_advisory_xact_lock(hashtextextended(NEW.company_id::text, 35006));
  SELECT * INTO source_request FROM fincilia.accounting_period_reopen_request
  WHERE request_id = NEW.request_id AND company_id = NEW.company_id;
  IF source_request.request_id IS NULL OR source_request.requested_by = NEW.decided_by THEN
    RAISE EXCEPTION 'reopen decision requires a different person'
      USING ERRCODE = '42501', CONSTRAINT = 'ck_period_reopen_sod';
  END IF;
  IF NEW.decision = 'approved'
     AND NEW.reason_code <> 'documented_basis_confirmed' THEN
    RAISE EXCEPTION 'approved reopen requires documented basis'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_period_reopen_positive';
  END IF;
  IF NEW.decision = 'rejected'
     AND NEW.reason_code = 'documented_basis_confirmed' THEN
    RAISE EXCEPTION 'rejected reopen requires a refusal reason'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_period_reopen_negative';
  END IF;
  RETURN NEW;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.validate_accounting_period_reopen_request()
  FROM PUBLIC;
REVOKE ALL ON FUNCTION fincilia.validate_accounting_period_reopen_decision()
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.validate_accounting_period_reopen_request(),
  fincilia.validate_accounting_period_reopen_decision()
  TO fincilia_app, fincilia_migrator;
CREATE TRIGGER accounting_period_reopen_request_guard
  BEFORE INSERT ON fincilia.accounting_period_reopen_request
  FOR EACH ROW EXECUTE FUNCTION fincilia.validate_accounting_period_reopen_request();
CREATE TRIGGER accounting_period_reopen_decision_guard
  BEFORE INSERT ON fincilia.accounting_period_reopen_decision
  FOR EACH ROW EXECUTE FUNCTION fincilia.validate_accounting_period_reopen_decision();

CREATE FUNCTION fincilia.guard_closed_period_financial_write()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  range_start date;
  range_end date;
  candidate record;
BEGIN
  PERFORM pg_advisory_xact_lock(hashtextextended(NEW.company_id::text, 35006));
  IF TG_TABLE_NAME = 'canonical_movement' THEN
    range_start := NEW.occurred_on;
    range_end := NEW.occurred_on;
  ELSIF TG_TABLE_NAME = 'account_balance' THEN
    range_start := (NEW.as_of AT TIME ZONE NEW.source_timezone)::date;
    range_end := range_start;
  ELSIF TG_TABLE_NAME = 'reconciliation_statement' THEN
    range_start := NEW.period_start;
    range_end := NEW.period_end;
  ELSIF TG_TABLE_NAME = 'source_expectation' THEN
    IF ROW(NEW.state, NEW.satisfied_by, NEW.satisfied_at, NEW.waived_reason)
       IS NOT DISTINCT FROM
       ROW(OLD.state, OLD.satisfied_by, OLD.satisfied_at, OLD.waived_reason) THEN
      RETURN NEW;
    END IF;
    range_start := NEW.period_start;
    range_end := NEW.period_end;
  ELSIF TG_TABLE_NAME = 'match_decision' THEN
    SELECT LEAST(left_movement.occurred_on, right_movement.occurred_on) AS start_on,
           GREATEST(left_movement.occurred_on, right_movement.occurred_on) AS end_on
      INTO candidate
    FROM fincilia.match_candidate c
    JOIN fincilia.canonical_movement left_movement
      ON left_movement.movement_id = c.left_movement_id
     AND left_movement.company_id = c.company_id
    JOIN fincilia.canonical_movement right_movement
      ON right_movement.movement_id = c.right_movement_id
     AND right_movement.company_id = c.company_id
    WHERE c.candidate_id = NEW.candidate_id AND c.company_id = NEW.company_id;
    range_start := candidate.start_on;
    range_end := candidate.end_on;
  ELSE
    RAISE EXCEPTION 'closed period guard attached to unsupported table'
      USING ERRCODE = '55000';
  END IF;

  IF range_start IS NULL OR range_end IS NULL OR fincilia.accounting_period_is_closed(
      NEW.company_id, range_start, range_end) THEN
    RAISE EXCEPTION 'financial write intersects a closed accounting period'
      USING ERRCODE = '55000', CONSTRAINT = 'ck_financial_write_period_open';
  END IF;
  RETURN NEW;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.guard_closed_period_financial_write() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.guard_closed_period_financial_write()
  TO fincilia_app, fincilia_migrator;

CREATE TRIGGER canonical_movement_period_open_guard
  BEFORE INSERT ON fincilia.canonical_movement
  FOR EACH ROW EXECUTE FUNCTION fincilia.guard_closed_period_financial_write();
CREATE TRIGGER account_balance_period_open_guard
  BEFORE INSERT ON fincilia.account_balance
  FOR EACH ROW EXECUTE FUNCTION fincilia.guard_closed_period_financial_write();
CREATE TRIGGER reconciliation_statement_period_open_guard
  BEFORE INSERT ON fincilia.reconciliation_statement
  FOR EACH ROW EXECUTE FUNCTION fincilia.guard_closed_period_financial_write();
CREATE TRIGGER source_expectation_period_open_guard
  BEFORE UPDATE ON fincilia.source_expectation
  FOR EACH ROW EXECUTE FUNCTION fincilia.guard_closed_period_financial_write();
CREATE TRIGGER match_decision_period_open_guard
  BEFORE INSERT ON fincilia.match_decision
  FOR EACH ROW EXECUTE FUNCTION fincilia.guard_closed_period_financial_write();

CREATE FUNCTION fincilia.reject_accounting_period_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
BEGIN
  RAISE EXCEPTION 'accounting period history is append-only' USING ERRCODE = '55000';
END
$function$;

REVOKE ALL ON FUNCTION fincilia.reject_accounting_period_mutation() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.reject_accounting_period_mutation()
  TO fincilia_app, fincilia_migrator;

CREATE TRIGGER accounting_period_close_append_only
  BEFORE UPDATE OR DELETE ON fincilia.accounting_period_close
  FOR EACH ROW EXECUTE FUNCTION fincilia.reject_accounting_period_mutation();
CREATE TRIGGER accounting_period_reopen_request_append_only
  BEFORE UPDATE OR DELETE ON fincilia.accounting_period_reopen_request
  FOR EACH ROW EXECUTE FUNCTION fincilia.reject_accounting_period_mutation();
CREATE TRIGGER accounting_period_reopen_decision_append_only
  BEFORE UPDATE OR DELETE ON fincilia.accounting_period_reopen_decision
  FOR EACH ROW EXECUTE FUNCTION fincilia.reject_accounting_period_mutation();
CREATE TRIGGER accounting_period_receipt_append_only
  BEFORE UPDATE OR DELETE ON fincilia.accounting_period_command_receipt
  FOR EACH ROW EXECUTE FUNCTION fincilia.reject_accounting_period_mutation();

ALTER TABLE fincilia.accounting_period_close ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.accounting_period_close FORCE ROW LEVEL SECURITY;
CREATE POLICY accounting_period_close_isolation ON fincilia.accounting_period_close
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));
ALTER TABLE fincilia.accounting_period_reopen_request ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.accounting_period_reopen_request FORCE ROW LEVEL SECURITY;
CREATE POLICY accounting_period_reopen_request_isolation
  ON fincilia.accounting_period_reopen_request
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));
ALTER TABLE fincilia.accounting_period_reopen_decision ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.accounting_period_reopen_decision FORCE ROW LEVEL SECURITY;
CREATE POLICY accounting_period_reopen_decision_isolation
  ON fincilia.accounting_period_reopen_decision
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));
ALTER TABLE fincilia.accounting_period_command_receipt ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.accounting_period_command_receipt FORCE ROW LEVEL SECURITY;
CREATE POLICY accounting_period_command_receipt_isolation
  ON fincilia.accounting_period_command_receipt
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

REVOKE ALL ON fincilia.accounting_period_close,
  fincilia.accounting_period_reopen_request,
  fincilia.accounting_period_reopen_decision,
  fincilia.accounting_period_command_receipt FROM PUBLIC;
GRANT SELECT, INSERT ON fincilia.accounting_period_close,
  fincilia.accounting_period_reopen_request,
  fincilia.accounting_period_reopen_decision,
  fincilia.accounting_period_command_receipt TO fincilia_app;
REVOKE UPDATE, DELETE ON fincilia.accounting_period_close,
  fincilia.accounting_period_reopen_request,
  fincilia.accounting_period_reopen_decision,
  fincilia.accounting_period_command_receipt FROM fincilia_app;
REVOKE ALL ON fincilia.accounting_period_close,
  fincilia.accounting_period_reopen_request,
  fincilia.accounting_period_reopen_decision,
  fincilia.accounting_period_command_receipt FROM fincilia_worker;

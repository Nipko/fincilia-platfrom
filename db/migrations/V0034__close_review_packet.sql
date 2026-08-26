-- FNC-CLS-005: expediente inmutable de revision de evidencia previa al cierre.
--
-- Ninguna fila de esta migracion cierra un periodo, certifica saldos, acepta
-- materialidad o crea un close_snapshot. El unico resultado positivo significa
-- que un revisor distinto observo la manifestacion diagnostica fijada.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

CREATE TABLE fincilia.close_review_packet (
  packet_id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id               uuid NOT NULL REFERENCES fincilia.company(company_id),
  period_start             date NOT NULL,
  period_end               date NOT NULL,
  version                  integer NOT NULL CHECK (version >= 1),
  manifest_schema_version  text NOT NULL CHECK (
                             manifest_schema_version = 'close-evidence-v1'),
  manifest                 jsonb NOT NULL,
  manifest_digest          char(64) NOT NULL CHECK (
                             manifest_digest ~ '^[0-9a-f]{64}$'),
  diagnostic_status        text NOT NULL CHECK (
                             diagnostic_status IN ('blocked', 'ready_for_review')),
  prepared_by              uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  assigned_reviewer_id     uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  prepared_at              timestamptz NOT NULL DEFAULT now(),
  audit_event_id           uuid NOT NULL,

  CONSTRAINT uq_close_review_packet_company UNIQUE (packet_id, company_id),
  CONSTRAINT uq_close_review_packet_version UNIQUE
    (company_id, period_start, period_end, version),
  CONSTRAINT fk_close_review_packet_audit FOREIGN KEY (audit_event_id, company_id)
    REFERENCES fincilia.audit_event(audit_event_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT ck_close_review_packet_period CHECK (period_end >= period_start),
  CONSTRAINT ck_close_review_packet_sod CHECK (prepared_by <> assigned_reviewer_id),
  CONSTRAINT ck_close_review_packet_manifest_size CHECK (
    pg_column_size(manifest) <= 524288)
);

CREATE TABLE fincilia.close_review_decision (
  decision_id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id               uuid NOT NULL REFERENCES fincilia.company(company_id),
  packet_id                uuid NOT NULL,
  decision                 text NOT NULL CHECK (
                             decision IN ('evidence_reviewed', 'changes_requested')),
  reason_code              text NOT NULL CHECK (reason_code IN (
                             'controls_reviewed', 'missing_evidence',
                             'inconsistent_scope', 'quality_blocker',
                             'lineage_gap', 'reconciliation_gap')),
  observed_manifest_digest char(64) NOT NULL CHECK (
                             observed_manifest_digest ~ '^[0-9a-f]{64}$'),
  decided_by               uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  decided_at               timestamptz NOT NULL DEFAULT now(),
  audit_event_id           uuid NOT NULL,

  CONSTRAINT uq_close_review_decision_company UNIQUE (decision_id, company_id),
  CONSTRAINT uq_close_review_decision_terminal UNIQUE (packet_id),
  CONSTRAINT fk_close_review_decision_packet FOREIGN KEY (packet_id, company_id)
    REFERENCES fincilia.close_review_packet(packet_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_close_review_decision_audit FOREIGN KEY (audit_event_id, company_id)
    REFERENCES fincilia.audit_event(audit_event_id, company_id) ON DELETE RESTRICT
);

CREATE TABLE fincilia.close_review_command_receipt (
  receipt_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id       uuid NOT NULL REFERENCES fincilia.company(company_id),
  actor_id         uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  action           text NOT NULL CHECK (
                     action IN ('prepare', 'evidence_reviewed', 'changes_requested')),
  idempotency_key  text NOT NULL CHECK (
                     length(idempotency_key) BETWEEN 16 AND 128
                     AND idempotency_key ~ '^[A-Za-z0-9._:-]+$'),
  request_digest   char(64) NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
  result_kind      text NOT NULL CHECK (result_kind IN ('packet', 'decision')),
  result_ref       uuid NOT NULL,
  created_at       timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_close_review_receipt_company UNIQUE (receipt_id, company_id),
  CONSTRAINT uq_close_review_receipt_key UNIQUE
    (company_id, actor_id, idempotency_key),
  CONSTRAINT ck_close_review_receipt_result CHECK (
    (action = 'prepare' AND result_kind = 'packet')
    OR (action IN ('evidence_reviewed', 'changes_requested')
        AND result_kind = 'decision'))
);

CREATE INDEX idx_close_review_packet_period ON fincilia.close_review_packet
  (company_id, period_end DESC, period_start DESC, version DESC, packet_id);
CREATE INDEX idx_close_review_packet_reviewer ON fincilia.close_review_packet
  (company_id, assigned_reviewer_id, prepared_at DESC, packet_id);
CREATE INDEX idx_close_review_decision_time ON fincilia.close_review_decision
  (company_id, decided_at DESC, decision_id);
CREATE INDEX idx_close_review_receipt_time ON fincilia.close_review_command_receipt
  (company_id, created_at DESC, receipt_id);

CREATE FUNCTION fincilia.is_close_reviewer_eligible(
  requested_company_id uuid, requested_subject_id uuid
) RETURNS boolean
LANGUAGE sql
STABLE
SET search_path = pg_catalog, fincilia
AS $function$
  SELECT EXISTS (
    SELECT 1
    FROM fincilia.engagement e
    JOIN fincilia.membership m ON m.firm_id = e.firm_id
    JOIN fincilia.subject s ON s.subject_id = m.subject_id
    JOIN fincilia.company_grant g
      ON g.company_id = e.company_id AND g.subject_id = m.subject_id
    WHERE e.company_id = requested_company_id
      AND m.subject_id = requested_subject_id
      AND e.status = 'active'
      AND (e.valid_to IS NULL OR e.valid_to >= CURRENT_DATE)
      AND m.status = 'active'
      AND s.status = 'active'
      AND s.subject_kind = 'person'
      AND g.revoked_at IS NULL
      AND g.company_role IN ('owner', 'reviewer')
  )
$function$;

REVOKE ALL ON FUNCTION fincilia.is_close_reviewer_eligible(uuid, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.is_close_reviewer_eligible(uuid, uuid)
  TO fincilia_app, fincilia_migrator;

CREATE FUNCTION fincilia.validate_close_review_packet()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  item jsonb;
  expected_source record;
  expected_statement record;
BEGIN
  IF NOT fincilia.is_close_reviewer_eligible(
      NEW.company_id, NEW.assigned_reviewer_id) THEN
    RAISE EXCEPTION 'assigned close reviewer is not eligible'
      USING ERRCODE = '42501';
  END IF;

  IF jsonb_typeof(NEW.manifest) <> 'object'
     OR (SELECT count(*) FROM jsonb_object_keys(NEW.manifest)) <> 5
     OR NOT NEW.manifest ?& ARRAY[
       'schema_version', 'diagnostic_status', 'controls', 'sources', 'accounts']
     OR NEW.manifest->>'schema_version' <> NEW.manifest_schema_version
     OR NEW.manifest->>'diagnostic_status' <> NEW.diagnostic_status
     OR jsonb_typeof(NEW.manifest->'controls') <> 'array'
     OR jsonb_typeof(NEW.manifest->'sources') <> 'array'
     OR jsonb_typeof(NEW.manifest->'accounts') <> 'array'
     OR jsonb_array_length(NEW.manifest->'controls') > 32
     OR jsonb_array_length(NEW.manifest->'sources') > 1200
     OR jsonb_array_length(NEW.manifest->'accounts') > 1200 THEN
    RAISE EXCEPTION 'close review manifest has an invalid envelope'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_close_manifest_envelope';
  END IF;

  FOR item IN SELECT value FROM jsonb_array_elements(NEW.manifest->'controls')
  LOOP
    IF jsonb_typeof(item) <> 'object'
       OR (SELECT count(*) FROM jsonb_object_keys(item)) <> 3
       OR NOT item ?& ARRAY['code', 'state', 'count']
       OR item->>'state' NOT IN ('pass', 'blocked', 'unavailable')
       OR jsonb_typeof(item->'count') <> 'number' THEN
      RAISE EXCEPTION 'close review control manifest is invalid'
        USING ERRCODE = '23514', CONSTRAINT = 'ck_close_manifest_control';
    END IF;
  END LOOP;

  FOR item IN SELECT value FROM jsonb_array_elements(NEW.manifest->'sources')
  LOOP
    IF jsonb_typeof(item) <> 'object'
       OR (SELECT count(*) FROM jsonb_object_keys(item)) <> 10
       OR NOT item ?& ARRAY[
         'expectation_id', 'data_source_id', 'financial_account_id',
         'expectation_state', 'dataset_version_id', 'dataset_state',
         'completeness_state', 'lineage_state', 'rejected_count', 'movement_count']
       OR jsonb_typeof(item->'rejected_count') <> 'number'
       OR jsonb_typeof(item->'movement_count') <> 'number' THEN
      RAISE EXCEPTION 'close review source manifest is invalid'
        USING ERRCODE = '23514', CONSTRAINT = 'ck_close_manifest_source';
    END IF;

    SELECT e.data_source_id, e.financial_account_id, e.satisfied_by
      INTO expected_source
    FROM fincilia.source_expectation e
    WHERE e.expectation_id = (item->>'expectation_id')::uuid
      AND e.company_id = NEW.company_id
      AND e.period_start = NEW.period_start
      AND e.period_end = NEW.period_end;
    IF expected_source IS NULL
       OR expected_source.data_source_id <> (item->>'data_source_id')::uuid
       OR expected_source.financial_account_id IS DISTINCT FROM
          NULLIF(item->>'financial_account_id', '')::uuid
       OR (item->>'dataset_version_id') IS NOT NULL AND NOT EXISTS (
         SELECT 1 FROM fincilia.dataset_version d
         WHERE d.dataset_version_id = (item->>'dataset_version_id')::uuid
           AND d.company_id = NEW.company_id
           AND d.artifact_id = expected_source.satisfied_by) THEN
      RAISE EXCEPTION 'close review source is outside its period scope'
        USING ERRCODE = '23514', CONSTRAINT = 'ck_close_manifest_source_scope';
    END IF;
  END LOOP;

  FOR item IN SELECT value FROM jsonb_array_elements(NEW.manifest->'accounts')
  LOOP
    IF jsonb_typeof(item) <> 'object'
       OR (SELECT count(*) FROM jsonb_object_keys(item)) <> 9
       OR NOT item ?& ARRAY[
         'financial_account_id', 'source_count', 'assessment_count',
         'statement_root_id', 'statement_id', 'statement_version',
         'statement_state', 'statement_lineage_state', 'coverage_state']
       OR jsonb_typeof(item->'source_count') <> 'number'
       OR jsonb_typeof(item->'assessment_count') <> 'number' THEN
      RAISE EXCEPTION 'close review account manifest is invalid'
        USING ERRCODE = '23514', CONSTRAINT = 'ck_close_manifest_account';
    END IF;
    IF NOT EXISTS (
      SELECT 1 FROM fincilia.financial_account a
      WHERE a.account_id = (item->>'financial_account_id')::uuid
        AND a.company_id = NEW.company_id) THEN
      RAISE EXCEPTION 'close review account is outside its company scope'
        USING ERRCODE = '23514', CONSTRAINT = 'ck_close_manifest_account_scope';
    END IF;
    IF (item->>'statement_id') IS NOT NULL THEN
      SELECT s.statement_root_id, s.version
        INTO expected_statement
      FROM fincilia.reconciliation_statement s
      WHERE s.statement_id = (item->>'statement_id')::uuid
        AND s.company_id = NEW.company_id
        AND s.financial_account_id = (item->>'financial_account_id')::uuid
        AND s.period_start = NEW.period_start
        AND s.period_end = NEW.period_end;
      IF expected_statement IS NULL
         OR expected_statement.statement_root_id <>
            (item->>'statement_root_id')::uuid
         OR expected_statement.version <> (item->>'statement_version')::integer THEN
        RAISE EXCEPTION 'close review statement is outside its account scope'
          USING ERRCODE = '23514', CONSTRAINT = 'ck_close_manifest_statement_scope';
      END IF;
    ELSIF (item->>'statement_root_id') IS NOT NULL
          OR (item->>'statement_version') IS NOT NULL THEN
      RAISE EXCEPTION 'close review statement identity is incomplete'
        USING ERRCODE = '23514', CONSTRAINT = 'ck_close_manifest_statement_identity';
    END IF;
  END LOOP;
  RETURN NEW;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.validate_close_review_packet() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.validate_close_review_packet()
  TO fincilia_app, fincilia_migrator;

CREATE TRIGGER close_review_packet_guard
  BEFORE INSERT ON fincilia.close_review_packet
  FOR EACH ROW EXECUTE FUNCTION fincilia.validate_close_review_packet();

CREATE FUNCTION fincilia.validate_close_review_decision()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  packet fincilia.close_review_packet%ROWTYPE;
BEGIN
  SELECT * INTO packet FROM fincilia.close_review_packet
  WHERE packet_id = NEW.packet_id AND company_id = NEW.company_id;
  IF packet.packet_id IS NULL THEN
    RAISE EXCEPTION 'close review packet is unavailable' USING ERRCODE = '23503';
  END IF;
  IF NEW.decided_by <> packet.assigned_reviewer_id
     OR NEW.decided_by = packet.prepared_by
     OR NOT fincilia.is_close_reviewer_eligible(NEW.company_id, NEW.decided_by) THEN
    RAISE EXCEPTION 'segregation of duties: assigned reviewer required'
      USING ERRCODE = '42501';
  END IF;
  IF NEW.observed_manifest_digest <> packet.manifest_digest THEN
    RAISE EXCEPTION 'reviewed manifest digest differs from the packet'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_close_review_digest';
  END IF;
  IF NEW.decision = 'evidence_reviewed' AND (
       packet.diagnostic_status <> 'ready_for_review'
       OR NEW.reason_code <> 'controls_reviewed') THEN
    RAISE EXCEPTION 'blocked evidence cannot be marked reviewed'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_close_review_positive';
  END IF;
  IF NEW.decision = 'changes_requested' AND NEW.reason_code = 'controls_reviewed' THEN
    RAISE EXCEPTION 'changes requested requires a blocking reason'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_close_review_negative';
  END IF;
  RETURN NEW;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.validate_close_review_decision() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.validate_close_review_decision()
  TO fincilia_app, fincilia_migrator;

CREATE TRIGGER close_review_decision_guard
  BEFORE INSERT ON fincilia.close_review_decision
  FOR EACH ROW EXECUTE FUNCTION fincilia.validate_close_review_decision();

CREATE FUNCTION fincilia.validate_close_review_receipt()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  stored_decision text;
BEGIN
  IF NEW.result_kind = 'packet' THEN
    PERFORM 1 FROM fincilia.close_review_packet
      WHERE packet_id = NEW.result_ref AND company_id = NEW.company_id;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'receipt packet result unavailable' USING ERRCODE = '23503';
    END IF;
  ELSE
    SELECT decision INTO stored_decision FROM fincilia.close_review_decision
      WHERE decision_id = NEW.result_ref AND company_id = NEW.company_id;
    IF stored_decision IS NULL OR stored_decision <> NEW.action THEN
      RAISE EXCEPTION 'receipt action does not match close review decision'
        USING ERRCODE = '23514';
    END IF;
  END IF;
  RETURN NEW;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.validate_close_review_receipt() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.validate_close_review_receipt()
  TO fincilia_app, fincilia_migrator;

CREATE TRIGGER close_review_receipt_guard
  BEFORE INSERT ON fincilia.close_review_command_receipt
  FOR EACH ROW EXECUTE FUNCTION fincilia.validate_close_review_receipt();

CREATE FUNCTION fincilia.reject_close_review_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
BEGIN
  RAISE EXCEPTION 'close review ledger is append-only' USING ERRCODE = '55000';
END
$function$;

REVOKE ALL ON FUNCTION fincilia.reject_close_review_mutation() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.reject_close_review_mutation()
  TO fincilia_app, fincilia_migrator;

CREATE TRIGGER close_review_packet_append_only
  BEFORE UPDATE OR DELETE ON fincilia.close_review_packet
  FOR EACH ROW EXECUTE FUNCTION fincilia.reject_close_review_mutation();
CREATE TRIGGER close_review_decision_append_only
  BEFORE UPDATE OR DELETE ON fincilia.close_review_decision
  FOR EACH ROW EXECUTE FUNCTION fincilia.reject_close_review_mutation();
CREATE TRIGGER close_review_receipt_append_only
  BEFORE UPDATE OR DELETE ON fincilia.close_review_command_receipt
  FOR EACH ROW EXECUTE FUNCTION fincilia.reject_close_review_mutation();

ALTER TABLE fincilia.close_review_packet ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.close_review_packet FORCE ROW LEVEL SECURITY;
CREATE POLICY close_review_packet_isolation ON fincilia.close_review_packet
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.close_review_decision ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.close_review_decision FORCE ROW LEVEL SECURITY;
CREATE POLICY close_review_decision_isolation ON fincilia.close_review_decision
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.close_review_command_receipt ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.close_review_command_receipt FORCE ROW LEVEL SECURITY;
CREATE POLICY close_review_receipt_isolation ON fincilia.close_review_command_receipt
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

REVOKE ALL ON fincilia.close_review_packet, fincilia.close_review_decision,
  fincilia.close_review_command_receipt FROM PUBLIC;
GRANT SELECT, INSERT ON fincilia.close_review_packet,
  fincilia.close_review_decision, fincilia.close_review_command_receipt
  TO fincilia_app;
REVOKE UPDATE, DELETE ON fincilia.close_review_packet,
  fincilia.close_review_decision, fincilia.close_review_command_receipt
  FROM fincilia_app;
REVOKE ALL ON fincilia.close_review_packet, fincilia.close_review_decision,
  fincilia.close_review_command_receipt FROM fincilia_worker;

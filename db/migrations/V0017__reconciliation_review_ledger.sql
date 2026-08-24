-- V0017: ledger local y sintetico de revision de candidatos de conciliacion.
--
-- Una fila confirma que alguien propuso o reviso un par; no confirma saldos, no
-- fusiona movimientos y no habilita auto-match. ADR-027 permanece Proposed.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

ALTER TABLE fincilia.audit_event
  ADD CONSTRAINT uq_audit_event_company UNIQUE (audit_event_id, company_id);

CREATE TABLE fincilia.match_candidate (
  candidate_id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id                uuid NOT NULL REFERENCES fincilia.company(company_id),
  left_movement_id          uuid NOT NULL,
  right_movement_id         uuid NOT NULL,
  rule_version              text NOT NULL CHECK (length(rule_version) BETWEEN 3 AND 80),
  signals                   text[] NOT NULL,
  date_window_days          smallint NOT NULL CHECK (date_window_days BETWEEN 0 AND 31),
  date_distance_days        smallint NOT NULL CHECK (date_distance_days BETWEEN 0 AND 31),
  engine_release_ids        uuid[] NOT NULL,
  canonical_schema_versions text[] NOT NULL,
  proposed_by               uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  proposed_at               timestamptz NOT NULL DEFAULT now(),
  audit_event_id            uuid NOT NULL,

  CONSTRAINT uq_match_candidate_company UNIQUE (candidate_id, company_id),
  CONSTRAINT uq_match_candidate_pair UNIQUE
    (company_id, rule_version, left_movement_id, right_movement_id),
  CONSTRAINT fk_match_left_movement FOREIGN KEY (left_movement_id, company_id)
    REFERENCES fincilia.canonical_movement (movement_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_match_right_movement FOREIGN KEY (right_movement_id, company_id)
    REFERENCES fincilia.canonical_movement (movement_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_match_candidate_audit FOREIGN KEY (audit_event_id, company_id)
    REFERENCES fincilia.audit_event (audit_event_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT ck_match_candidate_order CHECK (left_movement_id < right_movement_id),
  CONSTRAINT ck_match_candidate_signals CHECK (
    cardinality(signals) BETWEEN 5 AND 6
    AND signals <@ ARRAY[
      'exact_amount', 'same_currency', 'opposite_direction',
      'different_financial_account', 'date_within_explicit_window',
      'same_normalised_reference']::text[]),
  CONSTRAINT ck_match_candidate_release_evidence CHECK (
    cardinality(engine_release_ids) BETWEEN 1 AND 2
    AND cardinality(canonical_schema_versions) BETWEEN 1 AND 2)
);

CREATE INDEX idx_match_candidate_company_time
  ON fincilia.match_candidate (company_id, proposed_at DESC, candidate_id);
CREATE INDEX idx_match_candidate_left
  ON fincilia.match_candidate (company_id, left_movement_id);
CREATE INDEX idx_match_candidate_right
  ON fincilia.match_candidate (company_id, right_movement_id);

CREATE TABLE fincilia.match_decision (
  decision_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id           uuid NOT NULL REFERENCES fincilia.company(company_id),
  candidate_id         uuid NOT NULL,
  decision             text NOT NULL CHECK (decision IN ('confirmed', 'rejected')),
  reason_code          text NOT NULL CHECK (reason_code IN (
                         'documented_counterpart', 'documented_transfer',
                         'reference_supported', 'different_event',
                         'timing_mismatch', 'wrong_counterpart',
                         'insufficient_evidence')),
  evidence_refs        jsonb NOT NULL,
  decided_by           uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  decided_at           timestamptz NOT NULL DEFAULT now(),
  audit_event_id       uuid NOT NULL,

  CONSTRAINT uq_match_decision_company UNIQUE (decision_id, company_id),
  CONSTRAINT uq_match_decision_terminal UNIQUE (candidate_id),
  CONSTRAINT fk_match_decision_candidate FOREIGN KEY (candidate_id, company_id)
    REFERENCES fincilia.match_candidate (candidate_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_match_decision_audit FOREIGN KEY (audit_event_id, company_id)
    REFERENCES fincilia.audit_event (audit_event_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT ck_match_decision_evidence CHECK (
    jsonb_typeof(evidence_refs) = 'array'
    AND jsonb_array_length(evidence_refs) = 2
    AND pg_column_size(evidence_refs) <= 1024)
);

CREATE INDEX idx_match_decision_company_time
  ON fincilia.match_decision (company_id, decided_at DESC, decision_id);

CREATE TABLE fincilia.match_command_receipt (
  receipt_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id       uuid NOT NULL REFERENCES fincilia.company(company_id),
  actor_id         uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  action           text NOT NULL CHECK (action IN ('propose', 'confirm', 'reject')),
  idempotency_key  text NOT NULL CHECK (
                     length(idempotency_key) BETWEEN 16 AND 128
                     AND idempotency_key ~ '^[A-Za-z0-9._:-]+$'),
  request_digest   char(64) NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
  result_kind      text NOT NULL CHECK (result_kind IN ('candidate', 'decision')),
  result_ref       uuid NOT NULL,
  created_at       timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_match_receipt_company UNIQUE (receipt_id, company_id),
  CONSTRAINT uq_match_receipt_key UNIQUE (company_id, actor_id, idempotency_key),
  CONSTRAINT ck_match_receipt_action_result CHECK (
    (action = 'propose' AND result_kind = 'candidate')
    OR (action IN ('confirm', 'reject') AND result_kind = 'decision'))
);

CREATE INDEX idx_match_receipt_company_time
  ON fincilia.match_command_receipt (company_id, created_at DESC);

CREATE FUNCTION fincilia.enforce_match_decision_sod()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  author_id uuid;
  expected_left uuid;
  expected_right uuid;
BEGIN
  SELECT proposed_by, left_movement_id, right_movement_id
    INTO author_id, expected_left, expected_right
  FROM fincilia.match_candidate
  WHERE candidate_id = NEW.candidate_id AND company_id = NEW.company_id;

  IF author_id IS NULL THEN
    RAISE EXCEPTION 'candidate unavailable' USING ERRCODE = '23503';
  END IF;
  IF NEW.decision = 'confirmed' AND NEW.decided_by = author_id THEN
    RAISE EXCEPTION 'segregation of duties: proposer cannot confirm'
      USING ERRCODE = '42501';
  END IF;
  IF NEW.evidence_refs <> jsonb_build_array(
       jsonb_build_object('kind', 'movement', 'ref', expected_left::text),
       jsonb_build_object('kind', 'movement', 'ref', expected_right::text)) THEN
    RAISE EXCEPTION 'decision evidence must name the ordered candidate pair'
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.enforce_match_decision_sod() FROM PUBLIC;

CREATE TRIGGER match_decision_sod
  BEFORE INSERT ON fincilia.match_decision
  FOR EACH ROW EXECUTE FUNCTION fincilia.enforce_match_decision_sod();

CREATE FUNCTION fincilia.enforce_match_receipt_result()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  stored_decision text;
BEGIN
  IF NEW.result_kind = 'candidate' THEN
    PERFORM 1 FROM fincilia.match_candidate
      WHERE candidate_id = NEW.result_ref AND company_id = NEW.company_id;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'receipt candidate result unavailable' USING ERRCODE = '23503';
    END IF;
  ELSE
    SELECT decision INTO stored_decision FROM fincilia.match_decision
      WHERE decision_id = NEW.result_ref AND company_id = NEW.company_id;
    IF stored_decision IS NULL THEN
      RAISE EXCEPTION 'receipt decision result unavailable' USING ERRCODE = '23503';
    END IF;
    IF (NEW.action = 'confirm' AND stored_decision <> 'confirmed')
       OR (NEW.action = 'reject' AND stored_decision <> 'rejected') THEN
      RAISE EXCEPTION 'receipt action does not match decision result'
        USING ERRCODE = '23514';
    END IF;
  END IF;
  RETURN NEW;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.enforce_match_receipt_result() FROM PUBLIC;

CREATE TRIGGER match_receipt_result
  BEFORE INSERT ON fincilia.match_command_receipt
  FOR EACH ROW EXECUTE FUNCTION fincilia.enforce_match_receipt_result();

CREATE FUNCTION fincilia.reject_match_ledger_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
BEGIN
  RAISE EXCEPTION 'reconciliation review ledger is append-only'
    USING ERRCODE = '55000';
END
$function$;

REVOKE ALL ON FUNCTION fincilia.reject_match_ledger_mutation() FROM PUBLIC;

CREATE TRIGGER match_candidate_append_only
  BEFORE UPDATE OR DELETE ON fincilia.match_candidate
  FOR EACH ROW EXECUTE FUNCTION fincilia.reject_match_ledger_mutation();
CREATE TRIGGER match_decision_append_only
  BEFORE UPDATE OR DELETE ON fincilia.match_decision
  FOR EACH ROW EXECUTE FUNCTION fincilia.reject_match_ledger_mutation();
CREATE TRIGGER match_receipt_append_only
  BEFORE UPDATE OR DELETE ON fincilia.match_command_receipt
  FOR EACH ROW EXECUTE FUNCTION fincilia.reject_match_ledger_mutation();

ALTER TABLE fincilia.match_candidate ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.match_candidate FORCE ROW LEVEL SECURITY;
CREATE POLICY match_candidate_isolation ON fincilia.match_candidate
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.match_decision ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.match_decision FORCE ROW LEVEL SECURITY;
CREATE POLICY match_decision_isolation ON fincilia.match_decision
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.match_command_receipt ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.match_command_receipt FORCE ROW LEVEL SECURITY;
CREATE POLICY match_receipt_isolation ON fincilia.match_command_receipt
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

REVOKE ALL ON fincilia.match_candidate, fincilia.match_decision,
  fincilia.match_command_receipt FROM PUBLIC;
REVOKE UPDATE, DELETE ON fincilia.match_candidate, fincilia.match_decision,
  fincilia.match_command_receipt FROM fincilia_app;
GRANT SELECT, INSERT ON fincilia.match_candidate, fincilia.match_decision,
  fincilia.match_command_receipt TO fincilia_app;

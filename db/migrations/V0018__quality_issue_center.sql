-- V0018: centro operativo de alertas deterministas de calidad.
--
-- Las filas son senales para revision humana, no hechos financieros ni prueba
-- de fraude. No almacenan importes, descripciones, referencias o valores crudos
-- y ningun estado de esta tabla habilita publicacion, auto-match o cierre.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

CREATE TABLE fincilia.quality_issue (
  issue_id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id         uuid NOT NULL REFERENCES fincilia.company(company_id),
  issue_key          char(64) NOT NULL CHECK (issue_key ~ '^[0-9a-f]{64}$'),
  rule_code          text NOT NULL CHECK (rule_code IN (
                       'dataset_completeness_mismatch',
                       'dataset_completeness_unknown',
                       'dataset_rejected_records',
                       'lineage_invalidated',
                       'duplicate_fingerprint',
                       'reference_amount_conflict',
                       'posting_delay_over_31_days',
                       'amount_outlier_10x_median')),
  rule_version       text NOT NULL CHECK (length(rule_version) BETWEEN 3 AND 32),
  scope_kind         text NOT NULL CHECK (scope_kind IN ('dataset', 'movement')),
  scope_ref          uuid NOT NULL,
  severity           text NOT NULL CHECK (severity IN ('info', 'warning', 'high')),
  status             text NOT NULL DEFAULT 'open'
                       CHECK (status IN ('open', 'acknowledged', 'resolved', 'dismissed')),
  occurrence_count   integer NOT NULL DEFAULT 1 CHECK (occurrence_count >= 1),
  assigned_to        uuid REFERENCES fincilia.subject(subject_id),
  reviewed_by        uuid REFERENCES fincilia.subject(subject_id),
  reviewed_at        timestamptz,
  resolution_reason  text CHECK (resolution_reason IN (
                       'investigate', 'reviewed_source', 'corrected_upstream',
                       'duplicate_confirmed', 'expected_pattern',
                       'false_positive', 'not_applicable')),
  first_seen_at      timestamptz NOT NULL DEFAULT now(),
  last_seen_at       timestamptz NOT NULL DEFAULT now(),
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_quality_issue_company UNIQUE (issue_id, company_id),
  CONSTRAINT uq_quality_issue_key UNIQUE (company_id, issue_key),
  CONSTRAINT ck_quality_issue_times CHECK (
    first_seen_at <= last_seen_at AND created_at <= updated_at),
  CONSTRAINT ck_quality_issue_review CHECK (
    (status = 'open' AND reviewed_by IS NULL AND reviewed_at IS NULL
      AND resolution_reason IS NULL)
    OR (status = 'acknowledged' AND assigned_to IS NOT NULL
      AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL
      AND resolution_reason = 'investigate')
    OR (status IN ('resolved', 'dismissed') AND reviewed_by IS NOT NULL
      AND reviewed_at IS NOT NULL AND resolution_reason IS NOT NULL))
);

CREATE INDEX idx_quality_issue_company_status
  ON fincilia.quality_issue
  (company_id, status, severity, last_seen_at DESC, issue_id);
CREATE INDEX idx_quality_issue_company_rule
  ON fincilia.quality_issue (company_id, rule_code, last_seen_at DESC);

CREATE TABLE fincilia.quality_issue_event (
  event_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id        uuid NOT NULL REFERENCES fincilia.company(company_id),
  issue_id          uuid NOT NULL,
  from_status       text NOT NULL CHECK (from_status IN (
                      'open', 'acknowledged', 'resolved', 'dismissed')),
  to_status         text NOT NULL CHECK (to_status IN (
                      'acknowledged', 'resolved', 'dismissed')),
  reason_code       text NOT NULL CHECK (reason_code IN (
                      'investigate', 'reviewed_source', 'corrected_upstream',
                      'duplicate_confirmed', 'expected_pattern',
                      'false_positive', 'not_applicable')),
  rationale         text NOT NULL CHECK (length(rationale) BETWEEN 10 AND 500),
  actor_id          uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  audit_event_id    uuid NOT NULL,
  occurred_at       timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_quality_event_company UNIQUE (event_id, company_id),
  CONSTRAINT fk_quality_event_issue FOREIGN KEY (issue_id, company_id)
    REFERENCES fincilia.quality_issue (issue_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_quality_event_audit FOREIGN KEY (audit_event_id, company_id)
    REFERENCES fincilia.audit_event (audit_event_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT ck_quality_event_transition CHECK (
    (from_status = 'open' AND to_status IN ('acknowledged', 'resolved', 'dismissed'))
    OR (from_status = 'acknowledged' AND to_status IN ('resolved', 'dismissed')))
);

CREATE INDEX idx_quality_event_issue_time
  ON fincilia.quality_issue_event (company_id, issue_id, occurred_at DESC);

CREATE FUNCTION fincilia.enforce_quality_issue_update()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
BEGIN
  IF NEW.issue_id <> OLD.issue_id
     OR NEW.company_id <> OLD.company_id
     OR NEW.issue_key <> OLD.issue_key
     OR NEW.rule_code <> OLD.rule_code
     OR NEW.rule_version <> OLD.rule_version
     OR NEW.scope_kind <> OLD.scope_kind
     OR NEW.scope_ref <> OLD.scope_ref
     OR NEW.first_seen_at <> OLD.first_seen_at
     OR NEW.created_at <> OLD.created_at THEN
    RAISE EXCEPTION 'quality issue identity and evidence scope are immutable'
      USING ERRCODE = '55000';
  END IF;

  IF NEW.status <> OLD.status AND NOT (
       (OLD.status = 'open' AND NEW.status IN ('acknowledged', 'resolved', 'dismissed'))
       OR (OLD.status = 'acknowledged' AND NEW.status IN ('resolved', 'dismissed'))
     ) THEN
    RAISE EXCEPTION 'invalid quality issue transition'
      USING ERRCODE = '23514';
  END IF;

  IF NEW.last_seen_at < OLD.last_seen_at
     OR NEW.occurrence_count < OLD.occurrence_count THEN
    RAISE EXCEPTION 'quality issue observations are monotonic'
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.enforce_quality_issue_update() FROM PUBLIC;

CREATE TRIGGER quality_issue_update_guard
  BEFORE UPDATE ON fincilia.quality_issue
  FOR EACH ROW EXECUTE FUNCTION fincilia.enforce_quality_issue_update();

CREATE FUNCTION fincilia.reject_quality_issue_event_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
BEGIN
  RAISE EXCEPTION 'quality issue events are append-only' USING ERRCODE = '55000';
END
$function$;

REVOKE ALL ON FUNCTION fincilia.reject_quality_issue_event_mutation() FROM PUBLIC;

CREATE TRIGGER quality_issue_event_append_only
  BEFORE UPDATE OR DELETE ON fincilia.quality_issue_event
  FOR EACH ROW EXECUTE FUNCTION fincilia.reject_quality_issue_event_mutation();

ALTER TABLE fincilia.quality_issue ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.quality_issue FORCE ROW LEVEL SECURITY;
CREATE POLICY quality_issue_isolation ON fincilia.quality_issue
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.quality_issue_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.quality_issue_event FORCE ROW LEVEL SECURITY;
CREATE POLICY quality_issue_event_isolation ON fincilia.quality_issue_event
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

REVOKE ALL ON fincilia.quality_issue, fincilia.quality_issue_event FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE ON fincilia.quality_issue TO fincilia_app;
REVOKE DELETE ON fincilia.quality_issue FROM fincilia_app;
GRANT SELECT, INSERT ON fincilia.quality_issue_event TO fincilia_app;
REVOKE UPDATE, DELETE ON fincilia.quality_issue_event FROM fincilia_app;

-- V0035: borradores manuales de conciliacion 1:N y N:1.
--
-- La composicion usa movimientos completos e inmutables. No distribuye
-- importes, no reserva miembros, no confirma saldos y no alimenta cierres.
-- ADR-028 permanece Proposed y el alcance local sigue siendo sintetico.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

CREATE TABLE fincilia.match_group_candidate (
  group_candidate_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id                 uuid NOT NULL REFERENCES fincilia.company(company_id),
  anchor_dataset_version_id  uuid NOT NULL,
  related_dataset_version_id uuid NOT NULL,
  anchor_movement_id         uuid NOT NULL,
  related_movement_ids       uuid[] NOT NULL,
  rule_version               text NOT NULL CHECK (length(rule_version) BETWEEN 3 AND 80),
  proposed_by                uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  proposed_at                timestamptz NOT NULL DEFAULT now(),
  audit_event_id             uuid NOT NULL,

  CONSTRAINT uq_match_group_candidate_company
    UNIQUE (group_candidate_id, company_id),
  CONSTRAINT uq_match_group_candidate_composition
    UNIQUE (company_id, rule_version, anchor_movement_id, related_movement_ids),
  CONSTRAINT fk_match_group_anchor_dataset
    FOREIGN KEY (anchor_dataset_version_id, company_id)
    REFERENCES fincilia.dataset_version(dataset_version_id, company_id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_match_group_related_dataset
    FOREIGN KEY (related_dataset_version_id, company_id)
    REFERENCES fincilia.dataset_version(dataset_version_id, company_id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_match_group_anchor_movement
    FOREIGN KEY (anchor_movement_id, company_id)
    REFERENCES fincilia.canonical_movement(movement_id, company_id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_match_group_audit
    FOREIGN KEY (audit_event_id, company_id)
    REFERENCES fincilia.audit_event(audit_event_id, company_id)
    ON DELETE RESTRICT,
  CONSTRAINT ck_match_group_distinct_datasets
    CHECK (anchor_dataset_version_id <> related_dataset_version_id),
  CONSTRAINT ck_match_group_related_cardinality
    CHECK (array_ndims(related_movement_ids) = 1
           AND cardinality(related_movement_ids) BETWEEN 2 AND 49)
);

CREATE INDEX idx_match_group_company_time
  ON fincilia.match_group_candidate(company_id, proposed_at DESC,
                                     group_candidate_id);
CREATE INDEX idx_match_group_datasets
  ON fincilia.match_group_candidate(company_id, anchor_dataset_version_id,
                                     related_dataset_version_id, proposed_at DESC);
CREATE INDEX idx_match_group_related_members
  ON fincilia.match_group_candidate USING gin(related_movement_ids);

CREATE TABLE fincilia.match_group_command_receipt (
  receipt_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id         uuid NOT NULL REFERENCES fincilia.company(company_id),
  actor_id           uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  idempotency_key    text NOT NULL CHECK (
                       length(idempotency_key) BETWEEN 16 AND 128
                       AND idempotency_key ~ '^[A-Za-z0-9._:-]+$'),
  request_digest     char(64) NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
  group_candidate_id uuid NOT NULL,
  created_at         timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_match_group_receipt_company UNIQUE (receipt_id, company_id),
  CONSTRAINT uq_match_group_receipt_key
    UNIQUE (company_id, actor_id, idempotency_key),
  CONSTRAINT fk_match_group_receipt_result
    FOREIGN KEY (group_candidate_id, company_id)
    REFERENCES fincilia.match_group_candidate(group_candidate_id, company_id)
    ON DELETE RESTRICT
);

CREATE INDEX idx_match_group_receipt_company_time
  ON fincilia.match_group_command_receipt(company_id, created_at DESC);

CREATE FUNCTION fincilia.validate_match_group_candidate()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  canonical_related_ids uuid[];
  related_distinct_count bigint;
  anchor_currency text;
  anchor_direction text;
  anchor_account_id uuid;
  anchor_is_eligible boolean;
  related_count bigint;
  related_are_eligible boolean;
  audit_is_exact boolean;
BEGIN
  IF array_position(NEW.related_movement_ids, NULL) IS NOT NULL THEN
    RAISE EXCEPTION 'related movement identifiers cannot be null'
      USING ERRCODE = '23514';
  END IF;

  SELECT array_agg(item ORDER BY item), count(DISTINCT item)
    INTO canonical_related_ids, related_distinct_count
  FROM unnest(NEW.related_movement_ids) AS related(item);

  IF NEW.related_movement_ids IS DISTINCT FROM canonical_related_ids
     OR related_distinct_count <> cardinality(NEW.related_movement_ids) THEN
    RAISE EXCEPTION 'related movement identifiers must be unique and canonically ordered'
      USING ERRCODE = '23514';
  END IF;
  IF NEW.anchor_movement_id = ANY(NEW.related_movement_ids) THEN
    RAISE EXCEPTION 'anchor movement cannot also be related'
      USING ERRCODE = '23514';
  END IF;

  SELECT movement.currency_code, movement.direction,
         movement.financial_account_id,
         movement.dataset_version_id = NEW.anchor_dataset_version_id
         AND movement.state IN ('proposed', 'confirmed')
         AND movement.lineage_state = 'complete'
         AND dataset.state IN ('validated', 'published')
         AND dataset.completeness_state IN ('verified', 'accepted_exception')
         AND dataset.lineage_state = 'complete'
    INTO anchor_currency, anchor_direction, anchor_account_id,
         anchor_is_eligible
  FROM fincilia.canonical_movement movement
  JOIN fincilia.dataset_version dataset
    ON dataset.dataset_version_id = movement.dataset_version_id
   AND dataset.company_id = movement.company_id
  WHERE movement.company_id = NEW.company_id
    AND movement.movement_id = NEW.anchor_movement_id;

  IF anchor_currency IS NULL OR anchor_is_eligible IS NOT TRUE THEN
    RAISE EXCEPTION 'anchor movement is unavailable or ineligible'
      USING ERRCODE = '23514';
  END IF;

  SELECT count(*), bool_and(
           movement.dataset_version_id = NEW.related_dataset_version_id
           AND movement.currency_code = anchor_currency
           AND movement.direction <> anchor_direction
           AND movement.financial_account_id <> anchor_account_id
           AND movement.state IN ('proposed', 'confirmed')
           AND movement.lineage_state = 'complete'
           AND dataset.state IN ('validated', 'published')
           AND dataset.completeness_state IN ('verified', 'accepted_exception')
           AND dataset.lineage_state = 'complete')
    INTO related_count, related_are_eligible
  FROM unnest(NEW.related_movement_ids) AS requested(movement_id)
  JOIN fincilia.canonical_movement movement
    ON movement.company_id = NEW.company_id
   AND movement.movement_id = requested.movement_id
  JOIN fincilia.dataset_version dataset
    ON dataset.company_id = movement.company_id
   AND dataset.dataset_version_id = movement.dataset_version_id;

  IF related_count <> cardinality(NEW.related_movement_ids)
     OR related_are_eligible IS NOT TRUE THEN
    RAISE EXCEPTION 'related movements are unavailable or ineligible'
      USING ERRCODE = '23514';
  END IF;

  SELECT audit.company_id = NEW.company_id
         AND audit.subject_id = NEW.proposed_by
         AND audit.action = 'match.group.propose'
         AND audit.resource_kind = 'match_group_candidate'
         AND audit.resource_ref = NEW.group_candidate_id::text
         AND audit.outcome = 'allowed'
    INTO audit_is_exact
  FROM fincilia.audit_event audit
  WHERE audit.audit_event_id = NEW.audit_event_id
    AND audit.company_id = NEW.company_id;

  IF audit_is_exact IS NOT TRUE THEN
    RAISE EXCEPTION 'group proposal requires its exact allowed audit event'
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.validate_match_group_candidate() FROM PUBLIC;

CREATE TRIGGER match_group_candidate_validate
  BEFORE INSERT ON fincilia.match_group_candidate
  FOR EACH ROW EXECUTE FUNCTION fincilia.validate_match_group_candidate();

CREATE TRIGGER match_group_candidate_append_only
  BEFORE UPDATE OR DELETE ON fincilia.match_group_candidate
  FOR EACH ROW EXECUTE FUNCTION fincilia.reject_match_ledger_mutation();
CREATE TRIGGER match_group_receipt_append_only
  BEFORE UPDATE OR DELETE ON fincilia.match_group_command_receipt
  FOR EACH ROW EXECUTE FUNCTION fincilia.reject_match_ledger_mutation();

ALTER TABLE fincilia.match_group_candidate ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.match_group_candidate FORCE ROW LEVEL SECURITY;
CREATE POLICY match_group_candidate_isolation
  ON fincilia.match_group_candidate
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.match_group_command_receipt ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.match_group_command_receipt FORCE ROW LEVEL SECURITY;
CREATE POLICY match_group_receipt_isolation
  ON fincilia.match_group_command_receipt
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

REVOKE ALL ON fincilia.match_group_candidate,
  fincilia.match_group_command_receipt FROM PUBLIC;
REVOKE UPDATE, DELETE ON fincilia.match_group_candidate,
  fincilia.match_group_command_receipt FROM fincilia_app;
GRANT SELECT, INSERT ON fincilia.match_group_candidate,
  fincilia.match_group_command_receipt TO fincilia_app;

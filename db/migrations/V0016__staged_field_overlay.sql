-- FNC-CLN-001 — propuesta tipada y revision de una correccion por fila.
-- Aprobar no aplica: canonical_movement y el dataset base siguen inmutables.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

-- Las claves de tres columnas impiden que una propuesta combine un movimiento
-- o source record de otra version del dataset, incluso dentro de la empresa.
ALTER TABLE fincilia.canonical_movement
  ADD CONSTRAINT uq_movement_dataset_identity
  UNIQUE (movement_id, dataset_version_id, company_id);

ALTER TABLE fincilia.source_record
  ADD CONSTRAINT uq_source_record_dataset_identity
  UNIQUE (source_record_id, dataset_version_id, company_id);

CREATE TABLE fincilia.field_overlay (
  overlay_id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id                uuid NOT NULL REFERENCES fincilia.company(company_id),
  dataset_version_id        uuid NOT NULL,
  movement_id               uuid NOT NULL,
  source_record_id          uuid NOT NULL,
  target_field              text NOT NULL CHECK (target_field IN (
                              'amount', 'currency', 'direction', 'occurred_on',
                              'posted_on', 'value_date', 'accounting_date')),
  expected_base_digest      char(64) NOT NULL
                              CHECK (expected_base_digest ~ '^[0-9a-f]{64}$'),
  action                    text NOT NULL DEFAULT 'set_typed_value'
                              CHECK (action = 'set_typed_value'),
  value_type                text NOT NULL CHECK (value_type IN (
                              'money_decimal', 'currency_code',
                              'enum:direction', 'local_date')),
  proposed_value            text NOT NULL CHECK (
                              length(proposed_value) BETWEEN 1 AND 128),
  proposed_value_digest     char(64) NOT NULL
                              CHECK (proposed_value_digest ~ '^[0-9a-f]{64}$'),
  reason_code               text NOT NULL CHECK (reason_code IN (
                              'source_correction', 'bank_clarification',
                              'accounting_adjustment', 'date_correction',
                              'classification_correction', 'other_reviewed')),
  reason_comment            text NOT NULL CHECK (
                              octet_length(reason_comment) BETWEEN 1 AND 500),
  field_risk_class          text NOT NULL DEFAULT 'critical'
                              CHECK (field_risk_class = 'critical'),
  sequence                  integer NOT NULL CHECK (sequence >= 1),
  supersedes_overlay_id     uuid,
  created_by                uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  authorization_version     integer NOT NULL CHECK (authorization_version >= 1),
  engine_release_id         uuid NOT NULL REFERENCES fincilia.engine_release(release_id),
  canonical_schema_version  text NOT NULL
                              CHECK (length(canonical_schema_version) BETWEEN 1 AND 32),
  mapping_version_id        uuid NOT NULL,
  created_at                timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_field_overlay_identity UNIQUE (overlay_id, company_id),
  CONSTRAINT uq_field_overlay_sequence UNIQUE (
    dataset_version_id, movement_id, target_field, sequence),
  CONSTRAINT fk_field_overlay_dataset FOREIGN KEY (dataset_version_id, company_id)
    REFERENCES fincilia.dataset_version (dataset_version_id, company_id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_field_overlay_movement FOREIGN KEY (
    movement_id, dataset_version_id, company_id)
    REFERENCES fincilia.canonical_movement (
      movement_id, dataset_version_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_field_overlay_source FOREIGN KEY (
    source_record_id, dataset_version_id, company_id)
    REFERENCES fincilia.source_record (
      source_record_id, dataset_version_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_field_overlay_mapping FOREIGN KEY (mapping_version_id, company_id)
    REFERENCES fincilia.column_mapping_version (mapping_version_id, company_id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_field_overlay_supersedes FOREIGN KEY (
    supersedes_overlay_id, company_id)
    REFERENCES fincilia.field_overlay (overlay_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT ck_field_overlay_changes_value CHECK (
    expected_base_digest <> proposed_value_digest),
  CONSTRAINT ck_field_overlay_type_matches CHECK (
    (target_field = 'amount' AND value_type = 'money_decimal'
      AND proposed_value ~ '^[0-9]{1,26}\.[0-9]{12}$')
    OR (target_field = 'currency' AND value_type = 'currency_code'
      AND proposed_value ~ '^[A-Z]{3}$')
    OR (target_field = 'direction' AND value_type = 'enum:direction'
      AND proposed_value IN ('inflow', 'outflow'))
    OR (target_field IN ('occurred_on', 'posted_on', 'value_date', 'accounting_date')
      AND value_type = 'local_date'
      AND proposed_value ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'))
);

CREATE INDEX idx_field_overlay_dataset
  ON fincilia.field_overlay (dataset_version_id, created_at, overlay_id);

CREATE TABLE fincilia.field_overlay_review (
  review_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id      uuid NOT NULL REFERENCES fincilia.company(company_id),
  overlay_id      uuid NOT NULL,
  decision        text NOT NULL CHECK (decision IN ('approved', 'rejected')),
  reviewer_id     uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  rationale       text NOT NULL CHECK (octet_length(rationale) BETWEEN 1 AND 500),
  reviewed_at     timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_field_overlay_review_identity UNIQUE (review_id, company_id),
  CONSTRAINT uq_field_overlay_review_once UNIQUE (overlay_id),
  CONSTRAINT fk_field_overlay_review_overlay FOREIGN KEY (overlay_id, company_id)
    REFERENCES fincilia.field_overlay (overlay_id, company_id) ON DELETE RESTRICT
);

CREATE FUNCTION fincilia.field_overlay_review_enforces_sod()
RETURNS trigger
LANGUAGE plpgsql
AS $body$
DECLARE
  v_author uuid;
BEGIN
  SELECT created_by INTO v_author
    FROM fincilia.field_overlay
   WHERE overlay_id = NEW.overlay_id AND company_id = NEW.company_id;
  IF v_author IS NULL THEN
    RAISE EXCEPTION 'field overlay is not available in this company'
      USING ERRCODE = '23503';
  END IF;
  IF v_author = NEW.reviewer_id THEN
    RAISE EXCEPTION 'field overlay author cannot review their own proposal'
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$body$;

REVOKE ALL PRIVILEGES ON FUNCTION fincilia.field_overlay_review_enforces_sod()
  FROM PUBLIC;

CREATE TRIGGER field_overlay_review_sod
  BEFORE INSERT ON fincilia.field_overlay_review
  FOR EACH ROW EXECUTE FUNCTION fincilia.field_overlay_review_enforces_sod();

ALTER TABLE fincilia.field_overlay ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.field_overlay FORCE ROW LEVEL SECURITY;
CREATE POLICY field_overlay_isolation ON fincilia.field_overlay
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.field_overlay_review ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.field_overlay_review FORCE ROW LEVEL SECURITY;
CREATE POLICY field_overlay_review_isolation ON fincilia.field_overlay_review
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

GRANT SELECT, INSERT ON fincilia.field_overlay TO fincilia_app;
GRANT SELECT, INSERT ON fincilia.field_overlay_review TO fincilia_app;
REVOKE UPDATE, DELETE ON fincilia.field_overlay FROM fincilia_app;
REVOKE UPDATE, DELETE ON fincilia.field_overlay_review FROM fincilia_app;

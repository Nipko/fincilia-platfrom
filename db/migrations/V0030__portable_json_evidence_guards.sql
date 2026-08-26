-- FNC-CLS-003 — V0029 uso una funcion JSONB que PostgreSQL no ofrece.
-- Se conserva la regla exacta contando claves con jsonb_object_keys.

CREATE OR REPLACE FUNCTION fincilia.validate_completeness_control_evidence()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  assessment fincilia.completeness_assessment%ROWTYPE;
  evidence jsonb;
  ref_id uuid;
  dataset_seen boolean := false;
  expectation_seen boolean := false;
  valid_ref boolean;
BEGIN
  SELECT * INTO assessment
  FROM fincilia.completeness_assessment
  WHERE assessment_id = NEW.assessment_id AND company_id = NEW.company_id;
  IF assessment.assessment_id IS NULL THEN
    RAISE EXCEPTION 'control assessment is unavailable'
      USING ERRCODE = '23503';
  END IF;

  FOR evidence IN SELECT value FROM jsonb_array_elements(NEW.evidence_refs)
  LOOP
    IF jsonb_typeof(evidence) <> 'object'
       OR (SELECT count(*) FROM jsonb_object_keys(evidence)) <> 2
       OR NOT evidence ? 'kind' OR NOT evidence ? 'ref'
       OR (evidence->>'ref') !~
          '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$' THEN
      RAISE EXCEPTION 'control evidence reference is malformed'
        USING ERRCODE = '23514', CONSTRAINT = 'ck_control_evidence_reference';
    END IF;
    ref_id := (evidence->>'ref')::uuid;
    valid_ref := false;
    CASE evidence->>'kind'
      WHEN 'dataset_version' THEN
        valid_ref := ref_id = assessment.dataset_version_id;
        dataset_seen := dataset_seen OR valid_ref;
      WHEN 'source_expectation' THEN
        valid_ref := ref_id = assessment.source_expectation_id;
        expectation_seen := expectation_seen OR valid_ref;
      WHEN 'source_record' THEN
        SELECT EXISTS (
          SELECT 1 FROM fincilia.source_record s
          WHERE s.source_record_id = ref_id AND s.company_id = NEW.company_id
            AND s.dataset_version_id = assessment.dataset_version_id
            AND s.state = 'published' AND s.lineage_state = 'complete')
          INTO valid_ref;
      ELSE
        valid_ref := false;
    END CASE;
    IF NOT valid_ref THEN
      RAISE EXCEPTION 'control evidence is outside its assessment scope'
        USING ERRCODE = '23514', CONSTRAINT = 'ck_control_evidence_scope';
    END IF;
  END LOOP;
  IF NOT dataset_seen OR NOT expectation_seen THEN
    RAISE EXCEPTION 'control evidence must name dataset and expectation'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_control_evidence_minimum';
  END IF;
  RETURN NEW;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.validate_completeness_control_evidence() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.validate_completeness_control_evidence()
  TO fincilia_app, fincilia_migrator;

CREATE OR REPLACE FUNCTION fincilia.validate_reconciling_item_evidence()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  root fincilia.reconciliation_statement_root%ROWTYPE;
  evidence jsonb;
  ref_id uuid;
BEGIN
  SELECT * INTO root FROM fincilia.reconciliation_statement_root
  WHERE statement_root_id = NEW.statement_root_id AND company_id = NEW.company_id;
  IF root.statement_root_id IS NULL OR root.currency_code <> NEW.currency_code THEN
    RAISE EXCEPTION 'item scope differs from its statement root'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_item_statement_scope';
  END IF;
  FOR evidence IN SELECT value FROM jsonb_array_elements(NEW.evidence_refs)
  LOOP
    IF jsonb_typeof(evidence) <> 'object'
       OR (SELECT count(*) FROM jsonb_object_keys(evidence)) <> 2
       OR evidence->>'kind' <> 'source_record'
       OR (evidence->>'ref') !~
          '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$' THEN
      RAISE EXCEPTION 'item evidence reference is malformed'
        USING ERRCODE = '23514', CONSTRAINT = 'ck_item_evidence_reference';
    END IF;
    ref_id := (evidence->>'ref')::uuid;
    IF NOT EXISTS (
      SELECT 1 FROM fincilia.source_record s
      WHERE s.source_record_id = ref_id AND s.company_id = NEW.company_id
        AND s.state = 'published' AND s.lineage_state = 'complete') THEN
      RAISE EXCEPTION 'item evidence is outside its company or not published'
        USING ERRCODE = '23514', CONSTRAINT = 'ck_item_evidence_scope';
    END IF;
  END LOOP;
  RETURN NEW;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.validate_reconciling_item_evidence() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.validate_reconciling_item_evidence()
  TO fincilia_app, fincilia_migrator;

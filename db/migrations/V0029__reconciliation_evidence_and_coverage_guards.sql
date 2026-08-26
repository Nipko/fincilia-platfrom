-- FNC-CLS-003 — endurecimiento forward-only encontrado al ejecutar V0028.
-- La base valida la evidencia y la cobertura aunque la escritura no pase por API.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

CREATE FUNCTION fincilia.validate_completeness_control_evidence()
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
       OR jsonb_object_length(evidence) <> 2
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

CREATE TRIGGER completeness_control_evidence_guard
  BEFORE INSERT ON fincilia.completeness_control_result
  FOR EACH ROW EXECUTE FUNCTION fincilia.validate_completeness_control_evidence();

CREATE FUNCTION fincilia.validate_reconciling_item_evidence()
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
       OR jsonb_object_length(evidence) <> 2
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

CREATE TRIGGER reconciling_item_evidence_guard
  BEFORE INSERT ON fincilia.reconciling_item
  FOR EACH ROW EXECUTE FUNCTION fincilia.validate_reconciling_item_evidence();

CREATE OR REPLACE FUNCTION fincilia.derive_reconciliation_statement()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  root fincilia.reconciliation_statement_root%ROWTYPE;
  bank_amount numeric(38, 12);
  bank_type text;
  bank_lineage text;
  bank_as_of date;
  bank_engine uuid;
  bank_schema text;
  books_amount numeric(38, 12);
  books_type text;
  books_lineage text;
  books_as_of date;
  books_engine uuid;
  books_schema text;
  assessment_count integer;
  distinct_assessment_sources integer;
  eligible_assessments integer;
  expected_sources integer;
  item_count integer;
  additions numeric(38, 12);
  deductions numeric(38, 12);
BEGIN
  PERFORM pg_advisory_xact_lock(hashtextextended(NEW.statement_root_id::text, 0));
  SELECT * INTO root FROM fincilia.reconciliation_statement_root
  WHERE statement_root_id = NEW.statement_root_id AND company_id = NEW.company_id;
  IF root.statement_root_id IS NULL
     OR NEW.financial_account_id <> root.financial_account_id
     OR NEW.period_start <> root.period_start OR NEW.period_end <> root.period_end
     OR NEW.currency_code <> root.currency_code THEN
    RAISE EXCEPTION 'statement scope differs from its stable root'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_statement_root_scope';
  END IF;

  SELECT b.amount, b.balance_type, b.lineage_state,
         (b.as_of AT TIME ZONE b.source_timezone)::date,
         b.engine_release_id, b.canonical_schema_version
    INTO bank_amount, bank_type, bank_lineage, bank_as_of, bank_engine, bank_schema
  FROM fincilia.account_balance b
  WHERE b.balance_id = NEW.bank_closing_balance_id
    AND b.company_id = NEW.company_id
    AND b.financial_account_id = NEW.financial_account_id
    AND b.currency_code = NEW.currency_code;
  SELECT b.amount, b.balance_type, b.lineage_state,
         (b.as_of AT TIME ZONE b.source_timezone)::date,
         b.engine_release_id, b.canonical_schema_version
    INTO books_amount, books_type, books_lineage, books_as_of, books_engine, books_schema
  FROM fincilia.account_balance b
  WHERE b.balance_id = NEW.books_closing_balance_id
    AND b.company_id = NEW.company_id
    AND b.financial_account_id = NEW.financial_account_id
    AND b.currency_code = NEW.currency_code;
  IF bank_amount IS NULL OR books_amount IS NULL
     OR bank_type <> 'closing' OR books_type <> 'ledger'
     OR bank_as_of NOT BETWEEN NEW.period_start AND NEW.period_end
     OR books_as_of NOT BETWEEN NEW.period_start AND NEW.period_end
     OR bank_engine <> books_engine OR bank_schema <> books_schema THEN
    RAISE EXCEPTION 'statement balances are outside its account, period or version'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_statement_balance_scope';
  END IF;

  IF cardinality(NEW.completeness_assessment_ids)
       <> cardinality(ARRAY(SELECT DISTINCT unnest(NEW.completeness_assessment_ids)))
     OR cardinality(NEW.confirmed_reconciling_item_ids)
       <> cardinality(ARRAY(SELECT DISTINCT unnest(NEW.confirmed_reconciling_item_ids))) THEN
    RAISE EXCEPTION 'statement input identifiers must be unique'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_statement_input_unique';
  END IF;

  SELECT count(*), count(DISTINCT data_source_id), count(*) FILTER (
           WHERE state = 'verified' AND lineage_state = 'complete'
             AND engine_release_id = bank_engine
             AND canonical_schema_version = bank_schema)
    INTO assessment_count, distinct_assessment_sources, eligible_assessments
  FROM fincilia.completeness_assessment
  WHERE assessment_id = ANY(NEW.completeness_assessment_ids)
    AND company_id = NEW.company_id
    AND (financial_account_id IS NULL OR financial_account_id = NEW.financial_account_id)
    AND period_start = NEW.period_start AND period_end = NEW.period_end;
  IF assessment_count <> cardinality(NEW.completeness_assessment_ids)
     OR distinct_assessment_sources <> assessment_count THEN
    RAISE EXCEPTION 'statement assessments are outside scope or repeat a source'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_statement_assessment_scope';
  END IF;
  SELECT count(*) INTO expected_sources
  FROM fincilia.source_expectation
  WHERE company_id = NEW.company_id
    AND financial_account_id = NEW.financial_account_id
    AND period_start = NEW.period_start AND period_end = NEW.period_end;

  SELECT count(*),
         coalesce(sum(amount) FILTER (WHERE adjustment_side = 'add_to_bank'), 0),
         coalesce(sum(amount) FILTER (WHERE adjustment_side = 'deduct_from_bank'), 0)
    INTO item_count, additions, deductions
  FROM fincilia.reconciling_item
  WHERE item_decision_id = ANY(NEW.confirmed_reconciling_item_ids)
    AND company_id = NEW.company_id AND statement_root_id = NEW.statement_root_id
    AND currency_code = NEW.currency_code AND state = 'confirmed'
    AND lineage_state = 'complete' AND engine_release_id = bank_engine
    AND canonical_schema_version = bank_schema;
  IF item_count <> cardinality(NEW.confirmed_reconciling_item_ids) THEN
    RAISE EXCEPTION 'statement item is not a confirmed eligible decision'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_statement_item_scope';
  END IF;

  NEW.version := coalesce((
    SELECT max(version) + 1 FROM fincilia.reconciliation_statement
    WHERE company_id = NEW.company_id AND statement_root_id = NEW.statement_root_id), 1);
  NEW.confirmed_additions_to_bank := additions;
  NEW.confirmed_deductions_from_bank := deductions;
  NEW.adjusted_bank_balance := bank_amount + additions - deductions;
  NEW.unexplained_difference := NEW.adjusted_bank_balance - books_amount;
  NEW.engine_release_id := bank_engine;
  NEW.canonical_schema_version := bank_schema;
  NEW.lineage_state := 'required_pending';
  NEW.state := CASE
    WHEN bank_lineage = 'complete' AND books_lineage = 'complete'
      AND eligible_assessments = assessment_count
      AND assessment_count = expected_sources AND expected_sources > 0
      AND NEW.unexplained_difference = 0 THEN 'balanced'
    ELSE 'review_required'
  END;
  RETURN NEW;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.derive_reconciliation_statement() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.derive_reconciliation_statement()
  TO fincilia_app, fincilia_migrator;

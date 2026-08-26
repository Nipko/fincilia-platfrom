-- FNC-CLS-003 — evaluaciones, partidas y estados de conciliacion de saldos.
--
-- Las cuatro entidades canonicas son inmutables/append-only. La tabla `root`
-- solo aporta identidad estable entre versiones: no contiene dinero, estado ni
-- autoridad financiera. Ninguna fila habilita cierre productivo.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

CREATE TABLE fincilia.completeness_assessment (
  assessment_id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id              uuid NOT NULL REFERENCES fincilia.company(company_id),
  data_source_id          uuid NOT NULL,
  source_expectation_id   uuid NOT NULL,
  financial_account_id    uuid,
  dataset_version_id      uuid NOT NULL,
  period_start            date NOT NULL,
  period_end              date NOT NULL,
  state                   text NOT NULL CHECK (state IN (
                            'verified', 'mismatch', 'unknown', 'accepted_exception')),
  assessment_key          char(64) NOT NULL CHECK (assessment_key ~ '^[0-9a-f]{64}$'),
  prepared_by             uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  engine_release_id       uuid NOT NULL REFERENCES fincilia.engine_release(release_id),
  canonical_schema_version text NOT NULL CHECK (
                            length(canonical_schema_version) BETWEEN 1 AND 32),
  lineage_state           text NOT NULL DEFAULT 'required_pending' CHECK (
                            lineage_state IN ('required_pending', 'complete', 'invalidated')),
  created_at              timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_completeness_assessment_identity
    UNIQUE (assessment_id, company_id),
  CONSTRAINT uq_completeness_assessment_key
    UNIQUE (company_id, assessment_key),
  CONSTRAINT fk_assessment_source FOREIGN KEY (data_source_id, company_id)
    REFERENCES fincilia.data_source(data_source_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_assessment_expectation FOREIGN KEY (source_expectation_id, company_id)
    REFERENCES fincilia.source_expectation(expectation_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_assessment_account FOREIGN KEY (financial_account_id, company_id)
    REFERENCES fincilia.financial_account(account_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_assessment_dataset FOREIGN KEY (dataset_version_id, company_id)
    REFERENCES fincilia.dataset_version(dataset_version_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT ck_assessment_period CHECK (period_end >= period_start)
);

CREATE TABLE fincilia.completeness_control_result (
  control_result_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id               uuid NOT NULL REFERENCES fincilia.company(company_id),
  assessment_id            uuid NOT NULL,
  control_type             text NOT NULL CHECK (control_type IN (
                             'record_count', 'debit_total', 'credit_total',
                             'opening_balance', 'closing_balance',
                             'running_balance_continuity', 'period_coverage',
                             'page_section_coverage', 'sequence_cursor',
                             'provenance_integrity', 'currency_consistency',
                             'account_identity')),
  required                 boolean NOT NULL,
  outcome                  text NOT NULL CHECK (outcome IN (
                             'match', 'mismatch', 'unknown', 'not_applicable')),
  expected_value           jsonb,
  observed_value           jsonb,
  value_type               text NOT NULL CHECK (length(value_type) BETWEEN 1 AND 64),
  tolerance_policy_id      uuid,
  evidence_refs            jsonb NOT NULL,
  rule_version             text NOT NULL CHECK (length(rule_version) BETWEEN 1 AND 64),
  reason                   text CHECK (reason IS NULL OR length(reason) BETWEEN 1 AND 500),
  engine_release_id        uuid NOT NULL REFERENCES fincilia.engine_release(release_id),
  canonical_schema_version text NOT NULL CHECK (
                             length(canonical_schema_version) BETWEEN 1 AND 32),
  lineage_state            text NOT NULL DEFAULT 'required_pending' CHECK (
                             lineage_state IN ('required_pending', 'complete', 'invalidated')),
  created_at               timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_completeness_control_identity
    UNIQUE (control_result_id, company_id),
  CONSTRAINT uq_completeness_control_type
    UNIQUE (company_id, assessment_id, control_type),
  CONSTRAINT fk_control_assessment FOREIGN KEY (assessment_id, company_id)
    REFERENCES fincilia.completeness_assessment(assessment_id, company_id)
    ON DELETE RESTRICT,
  CONSTRAINT ck_control_expected_bounded CHECK (
    expected_value IS NULL OR pg_column_size(expected_value) <= 4096),
  CONSTRAINT ck_control_observed_bounded CHECK (
    observed_value IS NULL OR pg_column_size(observed_value) <= 4096),
  CONSTRAINT ck_control_evidence CHECK (
    jsonb_typeof(evidence_refs) = 'array'
    AND jsonb_array_length(evidence_refs) > 0
    AND pg_column_size(evidence_refs) <= 16384),
  CONSTRAINT ck_control_unknown_reason CHECK (
    outcome NOT IN ('unknown', 'not_applicable') OR reason IS NOT NULL)
);

-- La evaluacion y sus resultados se insertan en la misma transaccion. Esta
-- comprobacion diferida evita una ventana en la que un assessment aparente
-- `verified` sin controles, incluso si se escribe por fuera de la API.
CREATE FUNCTION fincilia.validate_completeness_assessment()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  required_count integer;
  mismatch_count integer;
  unknown_count integer;
  expected_state text;
BEGIN
  SELECT count(*) FILTER (WHERE required),
         count(*) FILTER (WHERE required AND outcome = 'mismatch'),
         count(*) FILTER (WHERE required AND outcome IN ('unknown', 'not_applicable'))
    INTO required_count, mismatch_count, unknown_count
  FROM fincilia.completeness_control_result
  WHERE assessment_id = NEW.assessment_id AND company_id = NEW.company_id;

  expected_state := CASE
    WHEN mismatch_count > 0 THEN 'mismatch'
    WHEN required_count = 0 OR unknown_count > 0 THEN 'unknown'
    ELSE 'verified'
  END;
  IF NEW.state <> expected_state THEN
    RAISE EXCEPTION 'assessment state does not match its required controls'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_assessment_derived_state';
  END IF;
  RETURN NULL;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.validate_completeness_assessment() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.validate_completeness_assessment()
  TO fincilia_app, fincilia_migrator;

CREATE CONSTRAINT TRIGGER completeness_assessment_derived_state
  AFTER INSERT ON fincilia.completeness_assessment
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION fincilia.validate_completeness_assessment();

CREATE TABLE fincilia.reconciliation_statement_root (
  statement_root_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id               uuid NOT NULL REFERENCES fincilia.company(company_id),
  financial_account_id     uuid NOT NULL,
  period_start             date NOT NULL,
  period_end               date NOT NULL,
  currency_code            text NOT NULL CHECK (currency_code ~ '^[A-Z]{3}$'),
  prepared_by              uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  created_at               timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_statement_root_identity UNIQUE (statement_root_id, company_id),
  CONSTRAINT uq_statement_root_scope UNIQUE (
    company_id, financial_account_id, period_start, period_end, currency_code),
  CONSTRAINT fk_statement_root_account FOREIGN KEY (
    financial_account_id, company_id, currency_code)
    REFERENCES fincilia.financial_account(account_id, company_id, currency_code)
    ON DELETE RESTRICT,
  CONSTRAINT ck_statement_root_period CHECK (period_end >= period_start)
);

CREATE TABLE fincilia.reconciling_item (
  item_decision_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  item_root_id              uuid NOT NULL,
  company_id                uuid NOT NULL REFERENCES fincilia.company(company_id),
  statement_root_id         uuid NOT NULL,
  adjustment_side          text NOT NULL CHECK (
                            adjustment_side IN ('add_to_bank', 'deduct_from_bank')),
  amount                   numeric(38, 12) NOT NULL CHECK (amount > 0),
  currency_code            text NOT NULL CHECK (currency_code ~ '^[A-Z]{3}$'),
  reason_code              text NOT NULL CHECK (length(reason_code) BETWEEN 1 AND 64),
  state                    text NOT NULL CHECK (
                            state IN ('proposed', 'confirmed', 'rejected', 'reversed')),
  evidence_refs            jsonb NOT NULL,
  prepared_by              uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  approved_by              uuid REFERENCES fincilia.subject(subject_id),
  approved_at              timestamptz,
  decision_version         integer NOT NULL CHECK (decision_version >= 1),
  engine_release_id        uuid NOT NULL REFERENCES fincilia.engine_release(release_id),
  canonical_schema_version text NOT NULL CHECK (
                            length(canonical_schema_version) BETWEEN 1 AND 32),
  lineage_state            text NOT NULL DEFAULT 'required_pending' CHECK (
                            lineage_state IN ('required_pending', 'complete', 'invalidated')),
  created_at               timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_reconciling_item_identity UNIQUE (item_decision_id, company_id),
  CONSTRAINT uq_reconciling_item_version UNIQUE (
    company_id, item_root_id, decision_version),
  CONSTRAINT fk_item_statement_root FOREIGN KEY (statement_root_id, company_id)
    REFERENCES fincilia.reconciliation_statement_root(statement_root_id, company_id)
    ON DELETE RESTRICT,
  CONSTRAINT ck_item_evidence CHECK (
    jsonb_typeof(evidence_refs) = 'array'
    AND jsonb_array_length(evidence_refs) > 0
    AND pg_column_size(evidence_refs) <= 16384),
  CONSTRAINT ck_item_approval CHECK (
    (state = 'proposed' AND approved_by IS NULL AND approved_at IS NULL)
    OR (state IN ('confirmed', 'rejected', 'reversed')
        AND approved_by IS NOT NULL AND approved_at IS NOT NULL
        AND approved_by <> prepared_by)),
  CONSTRAINT ck_confirmed_item_lineage CHECK (
    state <> 'confirmed' OR lineage_state = 'complete')
);

CREATE FUNCTION fincilia.validate_reconciling_item_decision()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  previous fincilia.reconciling_item%ROWTYPE;
BEGIN
  PERFORM pg_advisory_xact_lock(hashtextextended(NEW.item_root_id::text, 0));
  SELECT * INTO previous
  FROM fincilia.reconciling_item
  WHERE company_id = NEW.company_id AND item_root_id = NEW.item_root_id
  ORDER BY decision_version DESC LIMIT 1;

  IF previous.item_decision_id IS NULL THEN
    IF NEW.decision_version <> 1 OR NEW.state <> 'proposed'
       OR NEW.item_root_id <> NEW.item_decision_id THEN
      RAISE EXCEPTION 'first reconciling item decision must be its proposed root'
        USING ERRCODE = '23514', CONSTRAINT = 'ck_item_first_decision';
    END IF;
  ELSE
    IF NEW.decision_version <> previous.decision_version + 1
       OR NEW.statement_root_id <> previous.statement_root_id
       OR NEW.adjustment_side <> previous.adjustment_side
       OR NEW.amount <> previous.amount
       OR NEW.currency_code <> previous.currency_code
       OR NEW.reason_code <> previous.reason_code
       OR NEW.evidence_refs <> previous.evidence_refs
       OR NEW.prepared_by <> previous.prepared_by
       OR NEW.engine_release_id <> previous.engine_release_id
       OR NEW.canonical_schema_version <> previous.canonical_schema_version THEN
      RAISE EXCEPTION 'reconciling item decision changes immutable evidence'
        USING ERRCODE = '23514', CONSTRAINT = 'ck_item_decision_version';
    END IF;
    IF NOT ((previous.state = 'proposed' AND NEW.state IN ('confirmed', 'rejected'))
            OR (previous.state = 'confirmed' AND NEW.state = 'reversed')) THEN
      RAISE EXCEPTION 'invalid reconciling item transition'
        USING ERRCODE = '23514', CONSTRAINT = 'ck_item_transition';
    END IF;
  END IF;
  RETURN NEW;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.validate_reconciling_item_decision() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.validate_reconciling_item_decision()
  TO fincilia_app, fincilia_migrator;

CREATE TRIGGER reconciling_item_decision_guard
  BEFORE INSERT ON fincilia.reconciling_item
  FOR EACH ROW EXECUTE FUNCTION fincilia.validate_reconciling_item_decision();

CREATE TABLE fincilia.reconciliation_statement (
  statement_id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id               uuid NOT NULL REFERENCES fincilia.company(company_id),
  statement_root_id        uuid NOT NULL,
  version                  integer NOT NULL CHECK (version >= 1),
  financial_account_id    uuid NOT NULL,
  period_start            date NOT NULL,
  period_end              date NOT NULL,
  currency_code           text NOT NULL CHECK (currency_code ~ '^[A-Z]{3}$'),
  bank_closing_balance_id uuid NOT NULL,
  books_closing_balance_id uuid NOT NULL,
  completeness_assessment_ids uuid[] NOT NULL,
  confirmed_reconciling_item_ids uuid[] NOT NULL DEFAULT '{}'::uuid[],
  confirmed_additions_to_bank numeric(38, 12) NOT NULL DEFAULT 0,
  confirmed_deductions_from_bank numeric(38, 12) NOT NULL DEFAULT 0,
  adjusted_bank_balance   numeric(38, 12) NOT NULL DEFAULT 0,
  unexplained_difference numeric(38, 12) NOT NULL DEFAULT 0,
  state                   text NOT NULL DEFAULT 'draft' CHECK (state IN (
                            'draft', 'review_required', 'balanced',
                            'exception_accepted', 'superseded')),
  statement_key           char(64) NOT NULL CHECK (statement_key ~ '^[0-9a-f]{64}$'),
  prepared_by             uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  engine_release_id       uuid NOT NULL REFERENCES fincilia.engine_release(release_id),
  canonical_schema_version text NOT NULL CHECK (
                            length(canonical_schema_version) BETWEEN 1 AND 32),
  rule_version_ids        jsonb NOT NULL,
  lineage_state           text NOT NULL DEFAULT 'required_pending' CHECK (
                            lineage_state IN ('required_pending', 'complete', 'invalidated')),
  created_at              timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_reconciliation_statement_identity UNIQUE (statement_id, company_id),
  CONSTRAINT uq_reconciliation_statement_version UNIQUE (
    company_id, statement_root_id, version),
  CONSTRAINT uq_reconciliation_statement_key UNIQUE (company_id, statement_key),
  CONSTRAINT fk_statement_root FOREIGN KEY (statement_root_id, company_id)
    REFERENCES fincilia.reconciliation_statement_root(statement_root_id, company_id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_statement_account FOREIGN KEY (
    financial_account_id, company_id, currency_code)
    REFERENCES fincilia.financial_account(account_id, company_id, currency_code)
    ON DELETE RESTRICT,
  CONSTRAINT fk_statement_bank_balance FOREIGN KEY (bank_closing_balance_id, company_id)
    REFERENCES fincilia.account_balance(balance_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_statement_books_balance FOREIGN KEY (books_closing_balance_id, company_id)
    REFERENCES fincilia.account_balance(balance_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT ck_statement_period CHECK (period_end >= period_start),
  CONSTRAINT ck_statement_assessments CHECK (
    cardinality(completeness_assessment_ids) BETWEEN 1 AND 1000),
  CONSTRAINT ck_statement_items CHECK (
    cardinality(confirmed_reconciling_item_ids) <= 1000),
  CONSTRAINT ck_statement_rules CHECK (
    jsonb_typeof(rule_version_ids) = 'array'
    AND jsonb_array_length(rule_version_ids) > 0
    AND pg_column_size(rule_version_ids) <= 16384),
  CONSTRAINT ck_statement_balanced_exact CHECK (
    state <> 'balanced' OR unexplained_difference = 0),
  CONSTRAINT ck_statement_no_exception_in_e0 CHECK (state <> 'exception_accepted')
);

CREATE FUNCTION fincilia.derive_reconciliation_statement()
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
  eligible_assessments integer;
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

  SELECT count(*), count(*) FILTER (
           WHERE state = 'verified' AND lineage_state = 'complete'
             AND engine_release_id = bank_engine
             AND canonical_schema_version = bank_schema)
    INTO assessment_count, eligible_assessments
  FROM fincilia.completeness_assessment
  WHERE assessment_id = ANY(NEW.completeness_assessment_ids)
    AND company_id = NEW.company_id
    AND (financial_account_id IS NULL OR financial_account_id = NEW.financial_account_id)
    AND period_start = NEW.period_start AND period_end = NEW.period_end;
  IF assessment_count <> cardinality(NEW.completeness_assessment_ids) THEN
    RAISE EXCEPTION 'statement assessment is outside its scope'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_statement_assessment_scope';
  END IF;

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
      AND NEW.unexplained_difference = 0 THEN 'balanced'
    ELSE 'review_required'
  END;
  RETURN NEW;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.derive_reconciliation_statement() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.derive_reconciliation_statement()
  TO fincilia_app, fincilia_migrator;

CREATE TRIGGER reconciliation_statement_derivation
  BEFORE INSERT ON fincilia.reconciliation_statement
  FOR EACH ROW EXECUTE FUNCTION fincilia.derive_reconciliation_statement();

CREATE FUNCTION fincilia.reject_balance_reconciliation_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
BEGIN
  RAISE EXCEPTION 'balance reconciliation facts are immutable'
    USING ERRCODE = '55000';
END
$function$;

REVOKE ALL ON FUNCTION fincilia.reject_balance_reconciliation_mutation() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.reject_balance_reconciliation_mutation()
  TO fincilia_app, fincilia_migrator;

CREATE TRIGGER completeness_assessment_immutable
  BEFORE UPDATE OR DELETE ON fincilia.completeness_assessment
  FOR EACH ROW EXECUTE FUNCTION fincilia.reject_balance_reconciliation_mutation();
CREATE TRIGGER completeness_control_immutable
  BEFORE UPDATE OR DELETE ON fincilia.completeness_control_result
  FOR EACH ROW EXECUTE FUNCTION fincilia.reject_balance_reconciliation_mutation();
CREATE TRIGGER statement_root_immutable
  BEFORE UPDATE OR DELETE ON fincilia.reconciliation_statement_root
  FOR EACH ROW EXECUTE FUNCTION fincilia.reject_balance_reconciliation_mutation();
CREATE TRIGGER reconciling_item_immutable
  BEFORE UPDATE OR DELETE ON fincilia.reconciling_item
  FOR EACH ROW EXECUTE FUNCTION fincilia.reject_balance_reconciliation_mutation();
CREATE TRIGGER reconciliation_statement_immutable
  BEFORE UPDATE OR DELETE ON fincilia.reconciliation_statement
  FOR EACH ROW EXECUTE FUNCTION fincilia.reject_balance_reconciliation_mutation();

CREATE INDEX idx_assessment_period ON fincilia.completeness_assessment(
  company_id, period_end DESC, data_source_id);
CREATE INDEX idx_control_assessment ON fincilia.completeness_control_result(
  company_id, assessment_id);
CREATE INDEX idx_statement_period ON fincilia.reconciliation_statement(
  company_id, period_end DESC, financial_account_id, currency_code);
CREATE INDEX idx_item_statement ON fincilia.reconciling_item(
  company_id, statement_root_id, item_root_id, decision_version DESC);

ALTER TABLE fincilia.completeness_assessment ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.completeness_assessment FORCE ROW LEVEL SECURITY;
CREATE POLICY completeness_assessment_isolation ON fincilia.completeness_assessment
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.completeness_control_result ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.completeness_control_result FORCE ROW LEVEL SECURITY;
CREATE POLICY completeness_control_isolation ON fincilia.completeness_control_result
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.reconciliation_statement_root ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.reconciliation_statement_root FORCE ROW LEVEL SECURITY;
CREATE POLICY reconciliation_statement_root_isolation
  ON fincilia.reconciliation_statement_root
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.reconciling_item ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.reconciling_item FORCE ROW LEVEL SECURITY;
CREATE POLICY reconciling_item_isolation ON fincilia.reconciling_item
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.reconciliation_statement ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.reconciliation_statement FORCE ROW LEVEL SECURITY;
CREATE POLICY reconciliation_statement_isolation ON fincilia.reconciliation_statement
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

REVOKE ALL ON fincilia.completeness_assessment,
  fincilia.completeness_control_result, fincilia.reconciliation_statement_root,
  fincilia.reconciling_item, fincilia.reconciliation_statement FROM PUBLIC;
GRANT SELECT, INSERT ON fincilia.completeness_assessment,
  fincilia.completeness_control_result, fincilia.reconciliation_statement_root,
  fincilia.reconciling_item, fincilia.reconciliation_statement TO fincilia_app;
REVOKE UPDATE, DELETE ON fincilia.completeness_assessment,
  fincilia.completeness_control_result, fincilia.reconciliation_statement_root,
  fincilia.reconciling_item, fincilia.reconciliation_statement FROM fincilia_app;
REVOKE ALL ON fincilia.completeness_assessment,
  fincilia.completeness_control_result, fincilia.reconciliation_statement_root,
  fincilia.reconciling_item, fincilia.reconciliation_statement FROM fincilia_worker;

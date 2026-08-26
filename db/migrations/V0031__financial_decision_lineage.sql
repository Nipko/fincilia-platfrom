-- FNC-LIN-001 — prueba materializada de linaje antes del cierre.
--
-- Las tablas financieras siguen siendo append-only. La unica mutacion nueva es
-- el sello unidireccional `required_pending -> complete` del statement, despues
-- de insertar sus nodos y aristas en la misma transaccion. El sello no cambia
-- dinero, inputs, reglas, actor ni version.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

CREATE FUNCTION fincilia.financial_lineage_complete(
  p_entity_type text,
  p_company_id uuid,
  p_entity_id uuid
) RETURNS boolean
LANGUAGE plpgsql
STABLE
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  expected_count integer;
  matched_count integer;
  direct_path boolean;
BEGIN
  IF p_entity_type = 'account_balance' THEN
    SELECT count(DISTINCT target.field_name) = 2
       AND count(DISTINCT target.field_name) FILTER (
             WHERE target.field_name IN ('amount', 'as_of')) = 2
      INTO direct_path
    FROM fincilia.account_balance balance
    JOIN fincilia.source_record source
      ON source.source_record_id = balance.source_record_id
     AND source.company_id = balance.company_id
    JOIN fincilia.dataset_version dataset
      ON dataset.dataset_version_id = source.dataset_version_id
     AND dataset.company_id = source.company_id
    JOIN fincilia.lineage_node target
      ON target.company_id = balance.company_id
     AND target.node_type = 'financial_fact_field'
     AND target.entity_ref = balance.balance_id
    JOIN fincilia.lineage_edge edge
      ON edge.company_id = balance.company_id
     AND edge.to_node_id = target.node_id
     AND edge.operation = 'derived_from'
     AND edge.processing_run_id = dataset.processing_run_id
    JOIN fincilia.lineage_node source_node
      ON source_node.company_id = balance.company_id
     AND source_node.node_id = edge.from_node_id
     AND source_node.node_type = 'source_record_field'
     AND source_node.entity_ref = balance.source_record_id
    WHERE balance.company_id = p_company_id
      AND balance.balance_id = p_entity_id
      AND target.engine_release_id = balance.engine_release_id
      AND target.canonical_schema_version = balance.canonical_schema_version
      AND edge.engine_release_id = balance.engine_release_id
      AND edge.canonical_schema_version = balance.canonical_schema_version;
    RETURN coalesce(direct_path, false);

  ELSIF p_entity_type = 'completeness_control_result' THEN
    SELECT EXISTS (
      SELECT 1
      FROM fincilia.completeness_control_result control
      JOIN fincilia.completeness_assessment assessment
        ON assessment.assessment_id = control.assessment_id
       AND assessment.company_id = control.company_id
      JOIN fincilia.dataset_version dataset
        ON dataset.dataset_version_id = assessment.dataset_version_id
       AND dataset.company_id = assessment.company_id
      JOIN fincilia.lineage_node decision
        ON decision.company_id = control.company_id
       AND decision.node_type = 'decision'
       AND decision.entity_ref = control.control_result_id
       AND decision.field_name = 'control'
      JOIN fincilia.lineage_edge consumed
        ON consumed.company_id = control.company_id
       AND consumed.to_node_id = decision.node_id
       AND consumed.operation = 'decided_using'
       AND consumed.processing_run_id = dataset.processing_run_id
      JOIN fincilia.lineage_node fact
        ON fact.company_id = control.company_id
       AND fact.node_id = consumed.from_node_id
       AND fact.node_type = 'financial_fact_field'
       AND fact.entity_ref = control.control_result_id
       AND fact.field_name = 'dataset'
      JOIN fincilia.lineage_edge derived
        ON derived.company_id = control.company_id
       AND derived.to_node_id = fact.node_id
       AND derived.operation = 'derived_from'
       AND derived.processing_run_id = dataset.processing_run_id
      JOIN fincilia.lineage_node anchor
        ON anchor.company_id = control.company_id
       AND anchor.node_id = derived.from_node_id
       AND anchor.node_type = 'source_record_field'
       AND anchor.entity_ref = assessment.dataset_version_id
       AND anchor.field_name = 'dataset'
      WHERE control.company_id = p_company_id
        AND control.control_result_id = p_entity_id
        AND decision.engine_release_id = control.engine_release_id
        AND decision.canonical_schema_version = control.canonical_schema_version
    ) INTO direct_path;
    RETURN coalesce(direct_path, false);

  ELSIF p_entity_type = 'completeness_assessment' THEN
    SELECT count(*) INTO expected_count
    FROM fincilia.completeness_control_result control
    WHERE control.company_id = p_company_id
      AND control.assessment_id = p_entity_id
      AND control.lineage_state = 'complete';
    IF expected_count = 0 OR expected_count <> (
      SELECT count(*) FROM fincilia.completeness_control_result control
      WHERE control.company_id = p_company_id
        AND control.assessment_id = p_entity_id
    ) THEN
      RETURN false;
    END IF;
    SELECT count(DISTINCT control.control_result_id)
      INTO matched_count
    FROM fincilia.completeness_assessment assessment
    JOIN fincilia.lineage_node decision
      ON decision.company_id = assessment.company_id
     AND decision.node_type = 'decision'
     AND decision.entity_ref = assessment.assessment_id
     AND decision.field_name = 'assessment'
    JOIN fincilia.lineage_edge consumed
      ON consumed.company_id = assessment.company_id
     AND consumed.to_node_id = decision.node_id
     AND consumed.operation = 'decided_using'
    JOIN fincilia.lineage_node control_node
      ON control_node.company_id = assessment.company_id
     AND control_node.node_id = consumed.from_node_id
     AND control_node.node_type = 'decision'
     AND control_node.field_name = 'control'
    JOIN fincilia.completeness_control_result control
      ON control.company_id = assessment.company_id
     AND control.control_result_id = control_node.entity_ref
     AND control.assessment_id = assessment.assessment_id
     AND control.lineage_state = 'complete'
    WHERE assessment.company_id = p_company_id
      AND assessment.assessment_id = p_entity_id
      AND decision.engine_release_id = assessment.engine_release_id
      AND decision.canonical_schema_version = assessment.canonical_schema_version;
    RETURN matched_count = expected_count;

  ELSIF p_entity_type = 'reconciling_item' THEN
    SELECT cardinality(ARRAY(
      SELECT DISTINCT evidence->>'ref'
      FROM fincilia.reconciling_item item,
           jsonb_array_elements(item.evidence_refs) evidence
      WHERE item.company_id = p_company_id
        AND item.item_decision_id = p_entity_id
    )) INTO expected_count;
    SELECT count(DISTINCT fact.node_id)
      INTO matched_count
    FROM fincilia.reconciling_item item
    JOIN fincilia.lineage_node decision
      ON decision.company_id = item.company_id
     AND decision.node_type = 'decision'
     AND decision.entity_ref = item.item_decision_id
     AND decision.field_name = 'item'
    JOIN fincilia.lineage_edge consumed
      ON consumed.company_id = item.company_id
     AND consumed.to_node_id = decision.node_id
     AND consumed.operation = 'decided_using'
    JOIN fincilia.lineage_node fact
      ON fact.company_id = item.company_id
     AND fact.node_id = consumed.from_node_id
     AND fact.node_type = 'financial_fact_field'
     AND fact.entity_ref = item.item_decision_id
     AND fact.field_name LIKE 'evidence_%'
    JOIN fincilia.lineage_edge derived
      ON derived.company_id = item.company_id
     AND derived.to_node_id = fact.node_id
     AND derived.operation = 'derived_from'
    JOIN fincilia.lineage_node source_node
      ON source_node.company_id = item.company_id
     AND source_node.node_id = derived.from_node_id
     AND source_node.node_type = 'source_record_field'
    WHERE item.company_id = p_company_id
      AND item.item_decision_id = p_entity_id
      AND decision.engine_release_id = item.engine_release_id
      AND decision.canonical_schema_version = item.canonical_schema_version;
    RETURN expected_count > 0 AND matched_count = expected_count;

  ELSIF p_entity_type = 'reconciliation_statement' THEN
    SELECT 2 + cardinality(statement.completeness_assessment_ids)
             + cardinality(statement.confirmed_reconciling_item_ids)
      INTO expected_count
    FROM fincilia.reconciliation_statement statement
    WHERE statement.company_id = p_company_id
      AND statement.statement_id = p_entity_id;
    SELECT count(DISTINCT input.node_id)
      INTO matched_count
    FROM fincilia.reconciliation_statement statement
    JOIN fincilia.lineage_node decision
      ON decision.company_id = statement.company_id
     AND decision.node_type = 'decision'
     AND decision.entity_ref = statement.statement_id
     AND decision.field_name = 'statement'
    JOIN fincilia.lineage_edge consumed
      ON consumed.company_id = statement.company_id
     AND consumed.to_node_id = decision.node_id
     AND consumed.operation = 'decided_using'
    JOIN fincilia.lineage_node input
      ON input.company_id = statement.company_id
     AND input.node_id = consumed.from_node_id
    WHERE statement.company_id = p_company_id
      AND statement.statement_id = p_entity_id
      AND decision.engine_release_id = statement.engine_release_id
      AND decision.canonical_schema_version = statement.canonical_schema_version
      AND (
        (input.node_type = 'financial_fact_field'
         AND input.field_name = 'amount'
         AND input.entity_ref IN (
           statement.bank_closing_balance_id,
           statement.books_closing_balance_id))
        OR
        (input.node_type = 'decision'
         AND input.field_name = 'assessment'
         AND input.entity_ref = ANY(statement.completeness_assessment_ids))
        OR
        (input.node_type = 'decision'
         AND input.field_name = 'item'
         AND input.entity_ref = ANY(statement.confirmed_reconciling_item_ids))
      );
    RETURN expected_count IS NOT NULL AND matched_count = expected_count;
  END IF;
  RETURN false;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.financial_lineage_complete(text, uuid, uuid)
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.financial_lineage_complete(text, uuid, uuid)
  TO fincilia_app, fincilia_migrator;

CREATE FUNCTION fincilia.enforce_complete_financial_lineage()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  entity_id uuid;
BEGIN
  IF NEW.lineage_state <> 'complete' THEN
    RETURN NULL;
  END IF;
  entity_id := CASE TG_TABLE_NAME
    WHEN 'account_balance' THEN NEW.balance_id
    WHEN 'completeness_assessment' THEN NEW.assessment_id
    WHEN 'completeness_control_result' THEN NEW.control_result_id
    WHEN 'reconciling_item' THEN NEW.item_decision_id
    WHEN 'reconciliation_statement' THEN NEW.statement_id
  END;
  IF entity_id IS NULL OR NOT fincilia.financial_lineage_complete(
       TG_TABLE_NAME, NEW.company_id, entity_id) THEN
    RAISE EXCEPTION 'complete financial lineage is not materialized'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_financial_lineage_materialized';
  END IF;
  RETURN NULL;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.enforce_complete_financial_lineage() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.enforce_complete_financial_lineage()
  TO fincilia_app, fincilia_migrator;

CREATE CONSTRAINT TRIGGER account_balance_complete_lineage
  AFTER INSERT OR UPDATE ON fincilia.account_balance
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION fincilia.enforce_complete_financial_lineage();
CREATE CONSTRAINT TRIGGER completeness_assessment_complete_lineage
  AFTER INSERT OR UPDATE ON fincilia.completeness_assessment
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION fincilia.enforce_complete_financial_lineage();
CREATE CONSTRAINT TRIGGER completeness_control_complete_lineage
  AFTER INSERT OR UPDATE ON fincilia.completeness_control_result
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION fincilia.enforce_complete_financial_lineage();
CREATE CONSTRAINT TRIGGER reconciling_item_complete_lineage
  AFTER INSERT OR UPDATE ON fincilia.reconciling_item
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION fincilia.enforce_complete_financial_lineage();
CREATE CONSTRAINT TRIGGER reconciliation_statement_complete_lineage
  AFTER INSERT OR UPDATE ON fincilia.reconciliation_statement
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION fincilia.enforce_complete_financial_lineage();

-- V0028 rechazo toda mutacion. Se conserva esa politica y se abre solamente el
-- sello de linaje del statement: un cambio, en una direccion y con prueba real.
CREATE OR REPLACE FUNCTION fincilia.reject_balance_reconciliation_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  entity_id uuid;
BEGIN
  IF TG_OP = 'UPDATE'
     AND OLD.lineage_state = 'required_pending'
     AND NEW.lineage_state = 'complete'
     AND (to_jsonb(OLD) - 'lineage_state') = (to_jsonb(NEW) - 'lineage_state') THEN
    entity_id := CASE TG_TABLE_NAME
      WHEN 'reconciliation_statement' THEN NEW.statement_id
      ELSE NULL
    END;
    IF entity_id IS NOT NULL AND fincilia.financial_lineage_complete(
         TG_TABLE_NAME, NEW.company_id, entity_id) THEN
      RETURN NEW;
    END IF;
  END IF;
  RAISE EXCEPTION 'balance reconciliation facts are immutable'
    USING ERRCODE = '55000';
END
$function$;

REVOKE ALL ON FUNCTION fincilia.reject_balance_reconciliation_mutation() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.reject_balance_reconciliation_mutation()
  TO fincilia_app, fincilia_migrator;

GRANT UPDATE (lineage_state) ON fincilia.reconciliation_statement TO fincilia_app;

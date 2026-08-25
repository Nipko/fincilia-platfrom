-- FNC-LIN-001 — correccion forward-only de los triggers genericos de V0031.
--
-- Un RECORD de trigger no expone las columnas de otras tablas ni dentro de un
-- CASE que no se elige. Extraer el identificador desde su representacion jsonb
-- conserva una funcion unica sin referenciar campos inexistentes.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

CREATE OR REPLACE FUNCTION fincilia.enforce_complete_financial_lineage()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  entity_field text;
  entity_id uuid;
BEGIN
  IF NEW.lineage_state <> 'complete' THEN
    RETURN NULL;
  END IF;
  entity_field := CASE TG_TABLE_NAME
    WHEN 'account_balance' THEN 'balance_id'
    WHEN 'completeness_assessment' THEN 'assessment_id'
    WHEN 'completeness_control_result' THEN 'control_result_id'
    WHEN 'reconciling_item' THEN 'item_decision_id'
    WHEN 'reconciliation_statement' THEN 'statement_id'
  END;
  entity_id := (to_jsonb(NEW)->>entity_field)::uuid;
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
     AND (to_jsonb(OLD) - 'lineage_state') = (to_jsonb(NEW) - 'lineage_state')
     AND TG_TABLE_NAME = 'reconciliation_statement' THEN
    entity_id := (to_jsonb(NEW)->>'statement_id')::uuid;
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

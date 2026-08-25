-- FNC-LIN-001 — exactitud de la evidencia materializada.
--
-- V0031 introdujo el predicado base y V0032 hizo portables sus triggers. Esta
-- migracion es deliberadamente forward-only: conserva el predicado ya aplicado
-- y lo envuelve con dos comprobaciones que atan la decision al dataset o a los
-- source_record exactos declarados por la entidad financiera.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

ALTER FUNCTION fincilia.financial_lineage_complete(text, uuid, uuid)
  RENAME TO base_financial_lineage_complete;

REVOKE ALL ON FUNCTION
  fincilia.base_financial_lineage_complete(text, uuid, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
  fincilia.base_financial_lineage_complete(text, uuid, uuid)
  TO fincilia_app, fincilia_migrator;

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
  exact_path boolean;
BEGIN
  IF NOT fincilia.base_financial_lineage_complete(
      p_entity_type, p_company_id, p_entity_id) THEN
    RETURN false;
  END IF;

  IF p_entity_type = 'completeness_assessment' THEN
    SELECT EXISTS (
      SELECT 1
      FROM fincilia.completeness_assessment assessment
      JOIN fincilia.dataset_version dataset
        ON dataset.company_id = assessment.company_id
       AND dataset.dataset_version_id = assessment.dataset_version_id
      JOIN fincilia.lineage_node decision
        ON decision.company_id = assessment.company_id
       AND decision.node_type = 'decision'
       AND decision.entity_ref = assessment.assessment_id
       AND decision.field_name = 'assessment'
       AND decision.engine_release_id = assessment.engine_release_id
       AND decision.canonical_schema_version = assessment.canonical_schema_version
      JOIN fincilia.lineage_edge consumed
        ON consumed.company_id = assessment.company_id
       AND consumed.to_node_id = decision.node_id
       AND consumed.operation = 'decided_using'
       AND consumed.processing_run_id = dataset.processing_run_id
       AND consumed.engine_release_id = assessment.engine_release_id
       AND consumed.canonical_schema_version = assessment.canonical_schema_version
      JOIN fincilia.lineage_node fact
        ON fact.company_id = assessment.company_id
       AND fact.node_id = consumed.from_node_id
       AND fact.node_type = 'financial_fact_field'
       AND fact.entity_ref = assessment.assessment_id
       AND fact.field_name = 'dataset'
       AND fact.engine_release_id = assessment.engine_release_id
       AND fact.canonical_schema_version = assessment.canonical_schema_version
      JOIN fincilia.lineage_edge derived
        ON derived.company_id = assessment.company_id
       AND derived.to_node_id = fact.node_id
       AND derived.operation = 'derived_from'
       AND derived.processing_run_id = dataset.processing_run_id
       AND derived.engine_release_id = assessment.engine_release_id
       AND derived.canonical_schema_version = assessment.canonical_schema_version
      JOIN fincilia.lineage_node anchor
        ON anchor.company_id = assessment.company_id
       AND anchor.node_id = derived.from_node_id
       AND anchor.node_type = 'source_record_field'
       AND anchor.entity_ref = assessment.dataset_version_id
       AND anchor.field_name = 'dataset'
       AND anchor.engine_release_id = assessment.engine_release_id
       AND anchor.canonical_schema_version = assessment.canonical_schema_version
      WHERE assessment.company_id = p_company_id
        AND assessment.assessment_id = p_entity_id
    ) INTO exact_path;
    RETURN coalesce(exact_path, false);

  ELSIF p_entity_type = 'reconciling_item' THEN
    SELECT NOT EXISTS (
      SELECT 1
      FROM fincilia.reconciling_item item
      CROSS JOIN LATERAL jsonb_array_elements(item.evidence_refs)
        WITH ORDINALITY AS evidence(value, ordinal)
      WHERE item.company_id = p_company_id
        AND item.item_decision_id = p_entity_id
        AND NOT EXISTS (
          SELECT 1
          FROM fincilia.lineage_node decision
          JOIN fincilia.lineage_edge consumed
            ON consumed.company_id = item.company_id
           AND consumed.to_node_id = decision.node_id
           AND consumed.operation = 'decided_using'
           AND consumed.engine_release_id = item.engine_release_id
           AND consumed.canonical_schema_version = item.canonical_schema_version
          JOIN fincilia.lineage_node fact
            ON fact.company_id = item.company_id
           AND fact.node_id = consumed.from_node_id
           AND fact.node_type = 'financial_fact_field'
           AND fact.entity_ref = item.item_decision_id
           AND fact.field_name = format('evidence_%s',
                lpad(evidence.ordinal::text, 3, '0'))
           AND fact.engine_release_id = item.engine_release_id
           AND fact.canonical_schema_version = item.canonical_schema_version
          JOIN fincilia.lineage_edge derived
            ON derived.company_id = item.company_id
           AND derived.to_node_id = fact.node_id
           AND derived.operation = 'derived_from'
           AND derived.engine_release_id = item.engine_release_id
           AND derived.canonical_schema_version = item.canonical_schema_version
          JOIN fincilia.lineage_node source_node
            ON source_node.company_id = item.company_id
           AND source_node.node_id = derived.from_node_id
           AND source_node.node_type = 'source_record_field'
           AND source_node.entity_ref = (evidence.value->>'ref')::uuid
           AND source_node.field_name = 'record'
           AND source_node.engine_release_id = item.engine_release_id
           AND source_node.canonical_schema_version = item.canonical_schema_version
          WHERE decision.company_id = item.company_id
            AND decision.node_type = 'decision'
            AND decision.entity_ref = item.item_decision_id
            AND decision.field_name = 'item'
            AND decision.engine_release_id = item.engine_release_id
            AND decision.canonical_schema_version = item.canonical_schema_version
        )
    ) INTO exact_path;
    RETURN coalesce(exact_path, false);
  END IF;

  RETURN true;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.financial_lineage_complete(text, uuid, uuid)
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.financial_lineage_complete(text, uuid, uuid)
  TO fincilia_app, fincilia_migrator;

COMMENT ON FUNCTION fincilia.financial_lineage_complete(text, uuid, uuid) IS
  'Fail-closed exact materialized lineage predicate for complete financial entities.';

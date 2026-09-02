-- FNC-MAP-001: V0053 asegura el alta; este trigger adicional conserva la
-- misma invariante cuando el runtime avanza el estado de una version y dispone
-- por ello de UPDATE. La evidencia y la plantilla no pueden ser reetiquetadas.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

CREATE TRIGGER column_mapping_version_source_update_guard
  BEFORE UPDATE OF company_id, mapping_id, artifact_id
  ON fincilia.column_mapping_version
  FOR EACH ROW EXECUTE FUNCTION fincilia.enforce_mapping_artifact_source();

COMMENT ON TRIGGER column_mapping_version_source_update_guard
  ON fincilia.column_mapping_version IS
  'Preserves immutable source provenance when mapping version keys are updated.';

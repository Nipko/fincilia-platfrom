-- FNC-MAP-002: una version es evidencia reproducible. El runtime necesita
-- UPDATE para validarla, pero ese privilegio no autoriza reescribir su cuerpo
-- ni saltar o revertir la maquina de estados.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

CREATE FUNCTION fincilia.enforce_mapping_version_update()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $$
BEGIN
  IF NEW.mapping_version_id IS DISTINCT FROM OLD.mapping_version_id
     OR NEW.company_id IS DISTINCT FROM OLD.company_id
     OR NEW.mapping_id IS DISTINCT FROM OLD.mapping_id
     OR NEW.version_number IS DISTINCT FROM OLD.version_number
     OR NEW.artifact_id IS DISTINCT FROM OLD.artifact_id
     OR NEW.definition IS DISTINCT FROM OLD.definition
     OR NEW.definition_digest IS DISTINCT FROM OLD.definition_digest
     OR NEW.source_schema_digest IS DISTINCT FROM OLD.source_schema_digest
     OR NEW.created_by IS DISTINCT FROM OLD.created_by
     OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
    RAISE EXCEPTION 'mapping version payload and identity are immutable'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_mapping_version_immutable';
  END IF;

  -- Un UPDATE idempotente que no cambia estado ni metadatos es inocuo.
  IF NEW.state IS NOT DISTINCT FROM OLD.state
     AND NEW.validated_by IS NOT DISTINCT FROM OLD.validated_by
     AND NEW.validated_at IS NOT DISTINCT FROM OLD.validated_at THEN
    RETURN NEW;
  END IF;

  IF OLD.state = 'draft'
     AND NEW.state = 'validated'
     AND OLD.validated_by IS NULL
     AND OLD.validated_at IS NULL
     AND NEW.validated_by IS NOT NULL
     AND NEW.validated_at IS NOT NULL THEN
    RETURN NEW;
  END IF;

  IF OLD.state = 'validated'
     AND NEW.state = 'superseded'
     AND NEW.validated_by IS NOT DISTINCT FROM OLD.validated_by
     AND NEW.validated_at IS NOT DISTINCT FROM OLD.validated_at THEN
    RETURN NEW;
  END IF;

  RAISE EXCEPTION 'mapping version state transition is not allowed'
    USING ERRCODE = '23514',
          CONSTRAINT = 'ck_mapping_version_state_transition';
END
$$;

REVOKE ALL ON FUNCTION fincilia.enforce_mapping_version_update() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.enforce_mapping_version_update()
  TO fincilia_app, fincilia_migrator;

-- `source_*` se ejecuta antes alfabeticamente y conserva el error especifico
-- de FNC-MAP-001 cuando la mutacion intenta reetiquetar la evidencia.
CREATE TRIGGER column_mapping_version_state_payload_guard
  BEFORE UPDATE ON fincilia.column_mapping_version
  FOR EACH ROW EXECUTE FUNCTION fincilia.enforce_mapping_version_update();

COMMENT ON FUNCTION fincilia.enforce_mapping_version_update() IS
  'Preserves immutable mapping payload and draft-to-validated-to-superseded state.';

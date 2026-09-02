-- FNC-MAP-001: una plantilla de una fuente no puede mapear evidencia recibida
-- por otra. La fuente del artefacto es procedencia inmutable, no un dato que el
-- mapeo pueda reinterpretar.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM fincilia.column_mapping_version version
    JOIN fincilia.column_mapping mapping
      ON mapping.mapping_id = version.mapping_id
     AND mapping.company_id = version.company_id
    JOIN fincilia.source_artifact artifact
      ON artifact.artifact_id = version.artifact_id
     AND artifact.company_id = version.company_id
    WHERE artifact.data_source_id IS NULL
       OR artifact.data_source_id <> mapping.data_source_id
  ) THEN
    RAISE EXCEPTION 'existing mapping version has unverifiable source provenance'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_mapping_artifact_source';
  END IF;
END
$$;

CREATE FUNCTION fincilia.enforce_mapping_artifact_source()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $$
DECLARE
  mapping_source uuid;
  artifact_source uuid;
BEGIN
  SELECT data_source_id INTO mapping_source
  FROM fincilia.column_mapping
  WHERE mapping_id = NEW.mapping_id
    AND company_id = NEW.company_id;

  SELECT data_source_id INTO artifact_source
  FROM fincilia.source_artifact
  WHERE artifact_id = NEW.artifact_id
    AND company_id = NEW.company_id;

  IF mapping_source IS NULL
     OR artifact_source IS NULL
     OR mapping_source <> artifact_source THEN
    RAISE EXCEPTION 'mapping and artifact must belong to the same declared source'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_mapping_artifact_source';
  END IF;

  RETURN NEW;
END
$$;

REVOKE ALL ON FUNCTION fincilia.enforce_mapping_artifact_source() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.enforce_mapping_artifact_source()
  TO fincilia_app, fincilia_migrator;

CREATE TRIGGER column_mapping_version_source_guard
  BEFORE INSERT ON fincilia.column_mapping_version
  FOR EACH ROW EXECUTE FUNCTION fincilia.enforce_mapping_artifact_source();

COMMENT ON FUNCTION fincilia.enforce_mapping_artifact_source() IS
  'Fail-closed source provenance guard for immutable mapping versions.';

-- FNC-CLN-002: el runtime no recibe INSERT directo sobre processing_run.
-- Esta funcion estrecha registra solo una aplicacion sincrona ya terminada,
-- despues de revalidar la capability que la autorizo.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

GRANT CREATE ON SCHEMA fincilia TO fincilia_dispatch;
SET LOCAL ROLE fincilia_dispatch;

CREATE FUNCTION fincilia.record_overlay_application_run(
  p_company_id uuid,
  p_artifact_id uuid,
  p_issued_context_id uuid,
  p_result jsonb
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $record_overlay_run$
DECLARE
  v_run_id uuid := gen_random_uuid();
  v_version integer;
  v_attempt integer;
  v_now timestamptz := clock_timestamp();
BEGIN
  IF p_company_id IS NULL
     OR p_company_id::text IS DISTINCT FROM
        current_setting('fincilia.company_id', true) THEN
    RAISE EXCEPTION 'the company does not match the authorised context'
      USING ERRCODE = '42501';
  END IF;
  IF p_issued_context_id IS NULL OR p_result IS NULL
     OR jsonb_typeof(p_result) <> 'object'
     OR pg_column_size(p_result) > 65536 THEN
    RAISE EXCEPTION 'a bounded result and issued context are required'
      USING ERRCODE = '22023';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM fincilia.source_artifact artifact
     WHERE artifact.artifact_id = p_artifact_id
       AND artifact.company_id = p_company_id
  ) THEN
    RAISE EXCEPTION 'no such artifact in this context'
      USING ERRCODE = '42501';
  END IF;

  SELECT version.version INTO v_version
    FROM fincilia.authorization_version version
   WHERE version.company_id = p_company_id;

  IF v_version IS NULL OR NOT EXISTS (
    SELECT 1
      FROM fincilia.issued_authorization_context issued
      JOIN fincilia.subject subject_row
        ON subject_row.subject_id = issued.subject_id
      JOIN fincilia.engagement engagement
        ON engagement.engagement_id = issued.engagement_id
       AND engagement.company_id = issued.company_id
       AND engagement.firm_id = issued.firm_id
      JOIN fincilia.membership membership
        ON membership.subject_id = issued.subject_id
       AND membership.firm_id = issued.firm_id
     WHERE issued.context_id = p_issued_context_id
       AND issued.company_id = p_company_id
       AND issued.authorization_version = v_version
       AND issued.purpose_code = 'processing_job'
       AND issued.resource_kind = 'source_artifact'
       AND issued.expires_at > v_now
       AND subject_row.status = 'active'
       AND engagement.status = 'active'
       AND (engagement.valid_to IS NULL OR engagement.valid_to >= v_now::date)
       AND membership.status = 'active'
       AND EXISTS (
         SELECT 1 FROM fincilia.company_grant grant_row
          WHERE grant_row.company_id = issued.company_id
            AND grant_row.subject_id = issued.subject_id
            AND grant_row.revoked_at IS NULL
       )
       AND NOT EXISTS (
         SELECT 1 FROM fincilia.issued_authorization_revocation revoked
          WHERE revoked.company_id = issued.company_id
            AND revoked.context_id = issued.context_id
       )
  ) THEN
    RAISE EXCEPTION 'the issued authorization context is no longer valid'
      USING ERRCODE = '42501';
  END IF;

  PERFORM pg_advisory_xact_lock(
    hashtextextended('overlay-run:' || p_company_id::text || ':' ||
                     p_artifact_id::text, 24));
  SELECT coalesce(max(run.attempt), 0) + 1 INTO v_attempt
    FROM fincilia.processing_run run
   WHERE run.artifact_id = p_artifact_id
     AND run.kind = 'overlay_apply';

  INSERT INTO fincilia.processing_run (
    run_id, company_id, artifact_id, kind, status, attempt,
    started_at, finished_at, result, authorization_version, issued_context_id
  ) VALUES (
    v_run_id, p_company_id, p_artifact_id, 'overlay_apply', 'succeeded',
    v_attempt, v_now, v_now, p_result, v_version, p_issued_context_id
  );
  RETURN v_run_id;
END;
$record_overlay_run$;

ALTER FUNCTION fincilia.record_overlay_application_run(uuid, uuid, uuid, jsonb)
  OWNER TO fincilia_dispatch;
REVOKE ALL PRIVILEGES ON FUNCTION
  fincilia.record_overlay_application_run(uuid, uuid, uuid, jsonb)
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
  fincilia.record_overlay_application_run(uuid, uuid, uuid, jsonb)
  TO fincilia_app;

RESET ROLE;
REVOKE CREATE ON SCHEMA fincilia FROM fincilia_dispatch;

-- V0045: corrige ambiguedad de status y materializa altas/bajas de autoridad.
--
-- V0044 se conserva inmutable. Esta migracion tambien retira escrituras
-- directas heredadas del runtime sobre identidad: las altas ya atraviesan las
-- funciones acotadas de V0039/V0043 y los estados, las de este plano de control.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

REVOKE INSERT, UPDATE ON fincilia.subject, fincilia.identity_binding,
  fincilia.firm, fincilia.membership
FROM fincilia_app;

GRANT CREATE ON SCHEMA fincilia TO fincilia_identity;
SET LOCAL ROLE fincilia_identity;

CREATE OR REPLACE FUNCTION fincilia.platform_admin_set_subject_status(
  p_subject_id uuid,
  p_status text,
  p_reason_code text
)
RETURNS TABLE(subject_id text, display_name text, status text, created_at timestamptz)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  actor_id uuid;
  target_is_superadmin boolean;
BEGIN
  IF NOT fincilia.current_subject_has_platform_role(ARRAY['platform_superadmin']) THEN
    RAISE insufficient_privilege USING MESSAGE = 'platform access denied';
  END IF;
  actor_id := current_setting('fincilia.subject_id', true)::uuid;
  IF p_subject_id = actor_id OR p_status NOT IN ('active', 'suspended')
     OR p_reason_code !~ '^[a-z0-9._-]{3,80}$' THEN
    RAISE invalid_parameter_value USING MESSAGE = 'platform status change is invalid';
  END IF;

  SELECT EXISTS (
    SELECT 1 FROM fincilia.platform_role_assignment assignment
    WHERE assignment.subject_id = p_subject_id
      AND assignment.platform_role = 'platform_superadmin'
      AND assignment.status = 'active'
  ) INTO target_is_superadmin;
  IF p_status = 'suspended' AND target_is_superadmin AND (
    SELECT count(*) FROM fincilia.platform_role_assignment assignment
    JOIN fincilia.subject subject_row USING (subject_id)
    WHERE assignment.platform_role = 'platform_superadmin'
      AND assignment.status = 'active' AND subject_row.status = 'active'
  ) <= 1 THEN
    RAISE check_violation USING MESSAGE = 'the last platform superadmin must remain active';
  END IF;

  UPDATE fincilia.subject subject_row
  SET status = p_status
  WHERE subject_row.subject_id = p_subject_id
  RETURNING subject_row.subject_id::text, subject_row.display_name,
            subject_row.status, subject_row.created_at
  INTO subject_id, display_name, status, created_at;
  IF NOT FOUND THEN
    RAISE no_data_found USING MESSAGE = 'platform subject not found';
  END IF;

  INSERT INTO fincilia.platform_audit_event (
    platform_audit_event_id, actor_subject_id, action, resource_kind,
    resource_ref, outcome, detail
  ) VALUES (
    gen_random_uuid(), actor_id, 'platform.subject.status.change', 'subject',
    p_subject_id::text, 'allowed',
    jsonb_build_object('status', p_status, 'reason_code', p_reason_code)
  );
  RETURN NEXT;
END
$function$;

CREATE FUNCTION fincilia.platform_admin_grant_role(
  p_subject_id uuid,
  p_platform_role text,
  p_reason_code text
)
RETURNS TABLE(assignment_id text, subject_id text, platform_role text, status text,
              granted_at timestamptz)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  actor_id uuid;
BEGIN
  IF NOT fincilia.current_subject_has_platform_role(ARRAY['platform_superadmin']) THEN
    RAISE insufficient_privilege USING MESSAGE = 'platform access denied';
  END IF;
  actor_id := current_setting('fincilia.subject_id', true)::uuid;
  IF p_subject_id = actor_id
     OR p_platform_role NOT IN (
       'platform_superadmin', 'platform_operator', 'platform_auditor'
     )
     OR p_reason_code !~ '^[a-z0-9._-]{3,80}$'
     OR NOT EXISTS (
       SELECT 1 FROM fincilia.subject target
       WHERE target.subject_id = p_subject_id AND target.status = 'active'
     ) THEN
    RAISE invalid_parameter_value USING MESSAGE = 'platform role grant is invalid';
  END IF;

  SELECT assignment.assignment_id::text, assignment.subject_id::text,
         assignment.platform_role, assignment.status, assignment.granted_at
  INTO assignment_id, subject_id, platform_role, status, granted_at
  FROM fincilia.platform_role_assignment assignment
  WHERE assignment.subject_id = p_subject_id
    AND assignment.platform_role = p_platform_role
    AND assignment.status = 'active';
  IF FOUND THEN
    RETURN NEXT;
    RETURN;
  END IF;

  INSERT INTO fincilia.platform_role_assignment (
    assignment_id, subject_id, platform_role, grant_source, granted_by,
    reason_code
  ) VALUES (
    gen_random_uuid(), p_subject_id, p_platform_role, 'platform_admin',
    actor_id, p_reason_code
  )
  RETURNING platform_role_assignment.assignment_id::text,
            platform_role_assignment.subject_id::text,
            platform_role_assignment.platform_role,
            platform_role_assignment.status,
            platform_role_assignment.granted_at
  INTO assignment_id, subject_id, platform_role, status, granted_at;

  INSERT INTO fincilia.platform_audit_event (
    platform_audit_event_id, actor_subject_id, action, resource_kind,
    resource_ref, outcome, detail
  ) VALUES (
    gen_random_uuid(), actor_id, 'platform.role.grant', 'subject',
    p_subject_id::text, 'allowed', jsonb_build_object(
      'platform_role', p_platform_role, 'reason_code', p_reason_code
    )
  );
  RETURN NEXT;
END
$function$;

CREATE FUNCTION fincilia.platform_admin_revoke_role(
  p_subject_id uuid,
  p_platform_role text,
  p_reason_code text
)
RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  actor_id uuid;
  target_assignment uuid;
BEGIN
  IF NOT fincilia.current_subject_has_platform_role(ARRAY['platform_superadmin']) THEN
    RAISE insufficient_privilege USING MESSAGE = 'platform access denied';
  END IF;
  actor_id := current_setting('fincilia.subject_id', true)::uuid;
  IF p_subject_id = actor_id
     OR p_platform_role NOT IN (
       'platform_superadmin', 'platform_operator', 'platform_auditor'
     )
     OR p_reason_code !~ '^[a-z0-9._-]{3,80}$' THEN
    RAISE invalid_parameter_value USING MESSAGE = 'platform role revoke is invalid';
  END IF;

  SELECT assignment.assignment_id INTO target_assignment
  FROM fincilia.platform_role_assignment assignment
  WHERE assignment.subject_id = p_subject_id
    AND assignment.platform_role = p_platform_role
    AND assignment.status = 'active'
  FOR UPDATE;
  IF NOT FOUND THEN
    RETURN false;
  END IF;

  IF p_platform_role = 'platform_superadmin' AND (
    SELECT count(*) FROM fincilia.platform_role_assignment assignment
    JOIN fincilia.subject subject_row USING (subject_id)
    WHERE assignment.platform_role = 'platform_superadmin'
      AND assignment.status = 'active' AND subject_row.status = 'active'
  ) <= 1 THEN
    RAISE check_violation USING MESSAGE = 'the last platform superadmin must remain active';
  END IF;

  UPDATE fincilia.platform_role_assignment assignment
  SET status = 'revoked', revoked_by = actor_id, revoked_at = clock_timestamp()
  WHERE assignment.assignment_id = target_assignment;

  INSERT INTO fincilia.platform_audit_event (
    platform_audit_event_id, actor_subject_id, action, resource_kind,
    resource_ref, outcome, detail
  ) VALUES (
    gen_random_uuid(), actor_id, 'platform.role.revoke', 'subject',
    p_subject_id::text, 'allowed', jsonb_build_object(
      'platform_role', p_platform_role, 'reason_code', p_reason_code
    )
  );
  RETURN true;
END
$function$;

REVOKE ALL PRIVILEGES ON FUNCTION fincilia.platform_admin_grant_role(uuid, text, text) FROM PUBLIC;
REVOKE ALL PRIVILEGES ON FUNCTION fincilia.platform_admin_revoke_role(uuid, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.platform_admin_grant_role(uuid, text, text) TO fincilia_app;
GRANT EXECUTE ON FUNCTION fincilia.platform_admin_revoke_role(uuid, text, text) TO fincilia_app;
RESET ROLE;

REVOKE CREATE ON SCHEMA fincilia FROM fincilia_identity;

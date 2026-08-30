-- V0044: plano de administracion separado del tenancy financiero.
--
-- El rol de plataforma no es un company_role. Las tablas no se conceden al
-- runtime y toda operacion atraviesa funciones SECURITY DEFINER acotadas. El
-- primer superadmin se reclama una sola vez contra un binding Google verificado
-- que ya esta tokenizado con HMAC.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

CREATE TABLE fincilia.platform_bootstrap_control (
  singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
  expected_verified_email_ref text NOT NULL
    CHECK (expected_verified_email_ref ~ '^hmac-sha256:v1:[0-9a-f]{64}$'),
  configured_by text NOT NULL CHECK (length(configured_by) BETWEEN 3 AND 120),
  configuration_ref text NOT NULL CHECK (length(configuration_ref) BETWEEN 3 AND 200),
  configured_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  claimed_by uuid REFERENCES fincilia.subject(subject_id),
  claimed_at timestamptz,
  CHECK ((claimed_by IS NULL) = (claimed_at IS NULL))
);

CREATE TABLE fincilia.platform_role_assignment (
  assignment_id uuid PRIMARY KEY,
  subject_id uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  platform_role text NOT NULL CHECK (platform_role IN (
    'platform_superadmin', 'platform_operator', 'platform_auditor'
  )),
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
  grant_source text NOT NULL CHECK (grant_source IN ('initial_bootstrap', 'platform_admin')),
  granted_by uuid REFERENCES fincilia.subject(subject_id),
  reason_code text NOT NULL CHECK (reason_code ~ '^[a-z0-9._-]{3,80}$'),
  granted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  revoked_by uuid REFERENCES fincilia.subject(subject_id),
  revoked_at timestamptz,
  CHECK (
    (status = 'active' AND revoked_by IS NULL AND revoked_at IS NULL)
    OR (status = 'revoked' AND revoked_by IS NOT NULL AND revoked_at IS NOT NULL)
  ),
  CHECK (
    (grant_source = 'initial_bootstrap' AND granted_by IS NULL
      AND platform_role = 'platform_superadmin')
    OR (grant_source = 'platform_admin' AND granted_by IS NOT NULL)
  )
);

CREATE UNIQUE INDEX uq_platform_role_active
  ON fincilia.platform_role_assignment (subject_id, platform_role)
  WHERE status = 'active';

CREATE INDEX idx_platform_role_subject
  ON fincilia.platform_role_assignment (subject_id, granted_at DESC);

CREATE TABLE fincilia.platform_audit_event (
  platform_audit_event_id uuid PRIMARY KEY,
  actor_subject_id uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  action text NOT NULL CHECK (length(action) BETWEEN 3 AND 100),
  resource_kind text NOT NULL CHECK (length(resource_kind) BETWEEN 3 AND 80),
  resource_ref text NOT NULL CHECK (length(resource_ref) BETWEEN 1 AND 200),
  outcome text NOT NULL CHECK (outcome IN ('allowed', 'denied', 'error')),
  detail jsonb NOT NULL DEFAULT '{}'::jsonb,
  occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  CHECK (pg_column_size(detail) <= 4096)
);

CREATE INDEX idx_platform_audit_time
  ON fincilia.platform_audit_event (occurred_at DESC, platform_audit_event_id DESC);

REVOKE ALL PRIVILEGES ON fincilia.platform_bootstrap_control FROM PUBLIC, fincilia_app;
REVOKE ALL PRIVILEGES ON fincilia.platform_role_assignment FROM PUBLIC, fincilia_app;
REVOKE ALL PRIVILEGES ON fincilia.platform_audit_event FROM PUBLIC, fincilia_app;

GRANT SELECT, UPDATE ON fincilia.platform_bootstrap_control TO fincilia_identity;
GRANT SELECT, INSERT, UPDATE ON fincilia.platform_role_assignment TO fincilia_identity;
GRANT SELECT, INSERT ON fincilia.platform_audit_event TO fincilia_identity;
GRANT SELECT, UPDATE ON fincilia.subject TO fincilia_identity;
GRANT SELECT ON fincilia.identity_binding, fincilia.firm, fincilia.membership,
  fincilia.company TO fincilia_identity;

GRANT CREATE ON SCHEMA fincilia TO fincilia_identity;

CREATE FUNCTION fincilia.current_subject_has_platform_role(p_roles text[])
RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $function$
  SELECT EXISTS (
    SELECT 1
    FROM fincilia.platform_role_assignment role_assignment
    JOIN fincilia.subject subject_row
      ON subject_row.subject_id = role_assignment.subject_id
    WHERE role_assignment.subject_id::text =
            current_setting('fincilia.subject_id', true)
      AND role_assignment.status = 'active'
      AND role_assignment.platform_role = ANY (p_roles)
      AND subject_row.status = 'active'
  )
$function$;

ALTER FUNCTION fincilia.current_subject_has_platform_role(text[])
  OWNER TO fincilia_identity;

-- `company` conserva FORCE RLS. La autoridad ve exclusivamente metadatos al
-- ejecutar funciones de plataforma; no se abre ninguna tabla financiera.
CREATE POLICY company_platform_metadata_read ON fincilia.company
  FOR SELECT TO fincilia_identity
  USING (fincilia.current_subject_has_platform_role(ARRAY[
    'platform_superadmin', 'platform_operator', 'platform_auditor'
  ]));

CREATE FUNCTION fincilia.claim_initial_platform_superadmin(
  p_subject_id uuid,
  p_verified_email_ref text
)
RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  control_row fincilia.platform_bootstrap_control%ROWTYPE;
BEGIN
  IF p_subject_id::text IS DISTINCT FROM
       current_setting('fincilia.subject_id', true)
     OR p_verified_email_ref !~ '^hmac-sha256:v1:[0-9a-f]{64}$' THEN
    RETURN false;
  END IF;

  SELECT * INTO control_row
  FROM fincilia.platform_bootstrap_control
  WHERE singleton
  FOR UPDATE;

  IF NOT FOUND OR control_row.expected_verified_email_ref <> p_verified_email_ref THEN
    RETURN false;
  END IF;

  IF control_row.claimed_by IS NOT NULL THEN
    RETURN control_row.claimed_by = p_subject_id AND EXISTS (
      SELECT 1 FROM fincilia.platform_role_assignment
      WHERE subject_id = p_subject_id
        AND platform_role = 'platform_superadmin'
        AND status = 'active'
    );
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM fincilia.identity_binding binding
    JOIN fincilia.subject subject_row USING (subject_id)
    WHERE binding.subject_id = p_subject_id
      AND binding.verified_email_ref = p_verified_email_ref
      AND subject_row.status = 'active'
  ) THEN
    RETURN false;
  END IF;

  INSERT INTO fincilia.platform_role_assignment (
    assignment_id, subject_id, platform_role, grant_source, reason_code
  ) VALUES (
    gen_random_uuid(), p_subject_id, 'platform_superadmin',
    'initial_bootstrap', 'initial_platform_bootstrap'
  );

  UPDATE fincilia.platform_bootstrap_control
  SET claimed_by = p_subject_id, claimed_at = clock_timestamp()
  WHERE singleton;

  INSERT INTO fincilia.platform_audit_event (
    platform_audit_event_id, actor_subject_id, action, resource_kind,
    resource_ref, outcome, detail
  ) VALUES (
    gen_random_uuid(), p_subject_id, 'platform.bootstrap.claim', 'subject',
    p_subject_id::text, 'allowed', '{"role":"platform_superadmin"}'::jsonb
  );
  RETURN true;
END
$function$;

ALTER FUNCTION fincilia.claim_initial_platform_superadmin(uuid, text)
  OWNER TO fincilia_identity;

CREATE FUNCTION fincilia.platform_roles_for_current_subject()
RETURNS TABLE(platform_role text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $function$
  SELECT role_assignment.platform_role
  FROM fincilia.platform_role_assignment role_assignment
  JOIN fincilia.subject subject_row USING (subject_id)
  WHERE role_assignment.subject_id::text =
          current_setting('fincilia.subject_id', true)
    AND role_assignment.status = 'active'
    AND subject_row.status = 'active'
  ORDER BY role_assignment.platform_role
$function$;

ALTER FUNCTION fincilia.platform_roles_for_current_subject()
  OWNER TO fincilia_identity;

CREATE FUNCTION fincilia.platform_admin_overview()
RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $function$
BEGIN
  IF NOT fincilia.current_subject_has_platform_role(ARRAY[
       'platform_superadmin', 'platform_operator', 'platform_auditor'
     ]) THEN
    RAISE insufficient_privilege USING MESSAGE = 'platform access denied';
  END IF;

  RETURN jsonb_build_object(
    'subjects', jsonb_build_object(
      'total', (SELECT count(*) FROM fincilia.subject),
      'active', (SELECT count(*) FROM fincilia.subject WHERE status = 'active'),
      'suspended', (SELECT count(*) FROM fincilia.subject WHERE status = 'suspended')
    ),
    'firms', jsonb_build_object(
      'total', (SELECT count(*) FROM fincilia.firm),
      'active', (SELECT count(*) FROM fincilia.firm WHERE status = 'active'),
      'suspended', (SELECT count(*) FROM fincilia.firm WHERE status = 'suspended')
    ),
    'companies', jsonb_build_object(
      'total', (SELECT count(*) FROM fincilia.company),
      'active', (SELECT count(*) FROM fincilia.company WHERE status = 'active'),
      'suspended', (SELECT count(*) FROM fincilia.company WHERE status = 'suspended'),
      'archived', (SELECT count(*) FROM fincilia.company WHERE status = 'archived')
    ),
    'platform_roles', (SELECT count(*) FROM fincilia.platform_role_assignment
      WHERE status = 'active'),
    'bootstrap_claimed', EXISTS (
      SELECT 1 FROM fincilia.platform_bootstrap_control WHERE claimed_by IS NOT NULL
    )
  );
END
$function$;

ALTER FUNCTION fincilia.platform_admin_overview() OWNER TO fincilia_identity;

CREATE FUNCTION fincilia.platform_admin_identities(p_limit integer DEFAULT 50)
RETURNS TABLE(
  subject_id text,
  display_name text,
  status text,
  created_at timestamptz,
  active_firms bigint,
  platform_roles text[]
)
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $function$
BEGIN
  IF NOT fincilia.current_subject_has_platform_role(ARRAY[
       'platform_superadmin', 'platform_operator'
     ]) THEN
    RAISE insufficient_privilege USING MESSAGE = 'platform access denied';
  END IF;
  IF p_limit NOT BETWEEN 1 AND 100 THEN
    RAISE invalid_parameter_value USING MESSAGE = 'platform list limit is invalid';
  END IF;

  RETURN QUERY
  SELECT subject_row.subject_id::text, subject_row.display_name,
         subject_row.status, subject_row.created_at,
         count(DISTINCT membership.firm_id) FILTER (
           WHERE membership.status = 'active'
         )::bigint,
         coalesce(array_agg(DISTINCT role_assignment.platform_role) FILTER (
           WHERE role_assignment.status = 'active'
         ), ARRAY[]::text[])
  FROM fincilia.subject subject_row
  LEFT JOIN fincilia.membership membership
    ON membership.subject_id = subject_row.subject_id
  LEFT JOIN fincilia.platform_role_assignment role_assignment
    ON role_assignment.subject_id = subject_row.subject_id
  GROUP BY subject_row.subject_id
  ORDER BY subject_row.created_at DESC, subject_row.subject_id DESC
  LIMIT p_limit;
END
$function$;

ALTER FUNCTION fincilia.platform_admin_identities(integer) OWNER TO fincilia_identity;

CREATE FUNCTION fincilia.platform_admin_organizations(p_limit integer DEFAULT 50)
RETURNS TABLE(
  firm_id text,
  legal_name text,
  status text,
  created_at timestamptz,
  active_members bigint
)
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $function$
BEGIN
  IF NOT fincilia.current_subject_has_platform_role(ARRAY[
       'platform_superadmin', 'platform_operator', 'platform_auditor'
     ]) THEN
    RAISE insufficient_privilege USING MESSAGE = 'platform access denied';
  END IF;
  IF p_limit NOT BETWEEN 1 AND 100 THEN
    RAISE invalid_parameter_value USING MESSAGE = 'platform list limit is invalid';
  END IF;

  RETURN QUERY
  SELECT firm.firm_id::text, firm.legal_name, firm.status, firm.created_at,
         count(membership.membership_id) FILTER (
           WHERE membership.status = 'active'
         )::bigint
  FROM fincilia.firm firm
  LEFT JOIN fincilia.membership membership ON membership.firm_id = firm.firm_id
  GROUP BY firm.firm_id
  ORDER BY firm.created_at DESC, firm.firm_id DESC
  LIMIT p_limit;
END
$function$;

ALTER FUNCTION fincilia.platform_admin_organizations(integer)
  OWNER TO fincilia_identity;

CREATE FUNCTION fincilia.platform_admin_audit(p_limit integer DEFAULT 50)
RETURNS TABLE(
  event_id text,
  actor_subject_id text,
  actor_name text,
  action text,
  resource_kind text,
  resource_ref text,
  outcome text,
  detail jsonb,
  occurred_at timestamptz
)
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $function$
BEGIN
  IF NOT fincilia.current_subject_has_platform_role(ARRAY[
       'platform_superadmin', 'platform_operator', 'platform_auditor'
     ]) THEN
    RAISE insufficient_privilege USING MESSAGE = 'platform access denied';
  END IF;
  IF p_limit NOT BETWEEN 1 AND 100 THEN
    RAISE invalid_parameter_value USING MESSAGE = 'platform list limit is invalid';
  END IF;

  RETURN QUERY
  SELECT event.platform_audit_event_id::text,
         event.actor_subject_id::text, subject_row.display_name,
         event.action, event.resource_kind, event.resource_ref,
         event.outcome, event.detail, event.occurred_at
  FROM fincilia.platform_audit_event event
  JOIN fincilia.subject subject_row
    ON subject_row.subject_id = event.actor_subject_id
  ORDER BY event.occurred_at DESC, event.platform_audit_event_id DESC
  LIMIT p_limit;
END
$function$;

ALTER FUNCTION fincilia.platform_admin_audit(integer) OWNER TO fincilia_identity;

CREATE FUNCTION fincilia.platform_admin_set_subject_status(
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
    SELECT 1 FROM fincilia.platform_role_assignment
    WHERE subject_id = p_subject_id AND platform_role = 'platform_superadmin'
      AND status = 'active'
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

ALTER FUNCTION fincilia.platform_admin_set_subject_status(uuid, text, text)
  OWNER TO fincilia_identity;

REVOKE CREATE ON SCHEMA fincilia FROM fincilia_identity;

COMMENT ON TABLE fincilia.platform_role_assignment IS
  'Roles del plano de control; nunca conceden acceso financiero company-scoped.';
COMMENT ON TABLE fincilia.platform_bootstrap_control IS
  'Referencia HMAC singleton para reclamar exactamente un superadmin inicial.';
COMMENT ON TABLE fincilia.platform_audit_event IS
  'Auditoria append-only de administracion; metadatos sin payload financiero.';

SET LOCAL ROLE fincilia_identity;

REVOKE ALL PRIVILEGES ON FUNCTION fincilia.current_subject_has_platform_role(text[]) FROM PUBLIC;
REVOKE ALL PRIVILEGES ON FUNCTION fincilia.claim_initial_platform_superadmin(uuid, text) FROM PUBLIC;
REVOKE ALL PRIVILEGES ON FUNCTION fincilia.platform_roles_for_current_subject() FROM PUBLIC;
REVOKE ALL PRIVILEGES ON FUNCTION fincilia.platform_admin_overview() FROM PUBLIC;
REVOKE ALL PRIVILEGES ON FUNCTION fincilia.platform_admin_identities(integer) FROM PUBLIC;
REVOKE ALL PRIVILEGES ON FUNCTION fincilia.platform_admin_organizations(integer) FROM PUBLIC;
REVOKE ALL PRIVILEGES ON FUNCTION fincilia.platform_admin_audit(integer) FROM PUBLIC;
REVOKE ALL PRIVILEGES ON FUNCTION fincilia.platform_admin_set_subject_status(uuid, text, text) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION fincilia.current_subject_has_platform_role(text[]) TO fincilia_app;
GRANT EXECUTE ON FUNCTION fincilia.claim_initial_platform_superadmin(uuid, text) TO fincilia_app;
GRANT EXECUTE ON FUNCTION fincilia.platform_roles_for_current_subject() TO fincilia_app;
GRANT EXECUTE ON FUNCTION fincilia.platform_admin_overview() TO fincilia_app;
GRANT EXECUTE ON FUNCTION fincilia.platform_admin_identities(integer) TO fincilia_app;
GRANT EXECUTE ON FUNCTION fincilia.platform_admin_organizations(integer) TO fincilia_app;
GRANT EXECUTE ON FUNCTION fincilia.platform_admin_audit(integer) TO fincilia_app;
GRANT EXECUTE ON FUNCTION fincilia.platform_admin_set_subject_status(uuid, text, text) TO fincilia_app;

RESET ROLE;

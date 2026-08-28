-- V0041: identidad OIDC nominal e invitaciones vinculadas al correo verificado.
--
-- El correo y el `sub` nunca llegan en claro. La API los transforma con HMAC
-- dedicado antes de abrir la transaccion. La invitacion solo sirve para la
-- identidad de correo para la que fue emitida y se consume en el mismo commit
-- que crea subject, binding, firm y membership.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

CREATE TABLE fincilia.pilot_identity_invitation (
  invitation_id uuid PRIMARY KEY,
  code_digest text NOT NULL UNIQUE
    CHECK (code_digest ~ '^sha256:[0-9a-f]{64}$'),
  expected_email_ref text NOT NULL
    CHECK (expected_email_ref ~ '^hmac-sha256:v1:[0-9a-f]{64}$'),
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  consumed_at timestamptz,
  consumed_by uuid REFERENCES fincilia.subject(subject_id),
  revoked_at timestamptz,
  CONSTRAINT ck_pilot_identity_invitation_expiry
    CHECK (expires_at > created_at),
  CONSTRAINT ck_pilot_identity_invitation_consumption CHECK (
    (consumed_at IS NULL) = (consumed_by IS NULL)
  ),
  CONSTRAINT ck_pilot_identity_invitation_terminal CHECK (
    NOT (consumed_at IS NOT NULL AND revoked_at IS NOT NULL)
  )
);

REVOKE ALL PRIVILEGES ON fincilia.pilot_identity_invitation FROM PUBLIC;
REVOKE ALL PRIVILEGES ON fincilia.pilot_identity_invitation FROM fincilia_app;

CREATE INDEX idx_pilot_identity_invitation_open
  ON fincilia.pilot_identity_invitation (expires_at)
  WHERE consumed_at IS NULL AND revoked_at IS NULL;

GRANT CREATE ON SCHEMA fincilia TO fincilia_identity;
ALTER TABLE fincilia.pilot_identity_invitation OWNER TO fincilia_identity;

-- La autoridad NOLOGIN puede resolver el binding dentro de funciones acotadas.
-- El rol de la API no recupera SELECT directo sobre la tabla global.
GRANT SELECT ON fincilia.subject, fincilia.identity_binding TO fincilia_identity;

CREATE FUNCTION fincilia.resolve_external_identity(
  p_issuer text,
  p_external_subject_ref text
)
RETURNS TABLE(subject_id uuid, display_name text, status text)
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $function$
BEGIN
  IF p_issuer !~ '^https://[^[:space:][:cntrl:]]{3,500}$'
     OR p_external_subject_ref !~ '^hmac-sha256:v1:[0-9a-f]{64}$' THEN
    RAISE EXCEPTION 'managed identity is unavailable'
      USING ERRCODE = '22023';
  END IF;

  RETURN QUERY
  SELECT s.subject_id, s.display_name, s.status
  FROM fincilia.identity_binding AS b
  JOIN fincilia.subject AS s USING (subject_id)
  WHERE b.issuer = p_issuer
    AND b.external_subject_ref = p_external_subject_ref
  LIMIT 1;
END
$function$;

CREATE FUNCTION fincilia.register_external_account_with_invite(
  p_invite_code_digest text,
  p_verified_email_ref text,
  p_subject_id uuid,
  p_membership_id uuid,
  p_firm_id uuid,
  p_issuer text,
  p_external_subject_ref text,
  p_display_name text,
  p_firm_name text
)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  v_invitation_id uuid;
BEGIN
  IF p_invite_code_digest !~ '^sha256:[0-9a-f]{64}$'
     OR p_verified_email_ref !~ '^hmac-sha256:v1:[0-9a-f]{64}$'
     OR p_external_subject_ref !~ '^hmac-sha256:v1:[0-9a-f]{64}$'
     OR p_issuer !~ '^https://[^[:space:][:cntrl:]]{3,500}$' THEN
    RAISE EXCEPTION 'managed registration is unavailable'
      USING ERRCODE = '22023';
  END IF;

  IF length(btrim(p_display_name)) NOT BETWEEN 2 AND 200
     OR length(btrim(p_firm_name)) NOT BETWEEN 2 AND 300
     OR p_display_name ~ '[[:cntrl:]]'
     OR p_firm_name ~ '[[:cntrl:]]' THEN
    RAISE EXCEPTION 'managed registration profile is invalid'
      USING ERRCODE = '22023';
  END IF;

  SELECT invitation_id INTO v_invitation_id
  FROM fincilia.pilot_identity_invitation
  WHERE code_digest = p_invite_code_digest
    AND expected_email_ref = p_verified_email_ref
    AND consumed_at IS NULL
    AND revoked_at IS NULL
    AND expires_at > clock_timestamp()
  FOR UPDATE;

  IF v_invitation_id IS NULL THEN
    RAISE EXCEPTION 'managed registration is unavailable'
      USING ERRCODE = '22023';
  END IF;

  INSERT INTO fincilia.subject (
    subject_id, subject_kind, display_name, status
  ) VALUES (
    p_subject_id, 'person', btrim(p_display_name), 'active'
  );

  INSERT INTO fincilia.identity_binding (
    subject_id, issuer, external_subject_ref
  ) VALUES (
    p_subject_id, p_issuer, p_external_subject_ref
  );

  INSERT INTO fincilia.firm (firm_id, legal_name, status)
  VALUES (p_firm_id, btrim(p_firm_name), 'active');

  INSERT INTO fincilia.membership (
    membership_id, subject_id, firm_id, firm_role, status
  ) VALUES (
    p_membership_id, p_subject_id, p_firm_id, 'owner', 'active'
  );

  UPDATE fincilia.pilot_identity_invitation
  SET consumed_at = clock_timestamp(), consumed_by = p_subject_id
  WHERE invitation_id = v_invitation_id;
END
$function$;

ALTER FUNCTION fincilia.resolve_external_identity(text, text)
  OWNER TO fincilia_identity;
ALTER FUNCTION fincilia.register_external_account_with_invite(
  text, text, uuid, uuid, uuid, text, text, text, text
) OWNER TO fincilia_identity;

REVOKE CREATE ON SCHEMA fincilia FROM fincilia_identity;

SET LOCAL ROLE fincilia_identity;

REVOKE ALL PRIVILEGES ON FUNCTION
  fincilia.resolve_external_identity(text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
  fincilia.resolve_external_identity(text, text) TO fincilia_app;

REVOKE ALL PRIVILEGES ON FUNCTION
  fincilia.register_external_account_with_invite(
    text, text, uuid, uuid, uuid, text, text, text, text
  ) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
  fincilia.register_external_account_with_invite(
    text, text, uuid, uuid, uuid, text, text, text, text
  ) TO fincilia_app;

COMMENT ON TABLE fincilia.pilot_identity_invitation IS
  'Invitaciones nominales: solo digests y referencias HMAC, nunca correo o codigo.';
COMMENT ON FUNCTION fincilia.resolve_external_identity(text, text) IS
  'Resuelve una identidad externa exacta sin abrir lectura global al runtime.';
COMMENT ON FUNCTION fincilia.register_external_account_with_invite(
  text, text, uuid, uuid, uuid, text, text, text, text
) IS 'Alta OIDC atomica y vinculada a una invitacion nominal de un uso.';

RESET ROLE;

-- La API no necesita escribir identidad global directamente. Las operaciones
-- de alta pasan por las funciones anteriores y la gestion de roles usa
-- funciones company-scoped independientes.
REVOKE INSERT, UPDATE ON fincilia.subject, fincilia.membership FROM fincilia_app;

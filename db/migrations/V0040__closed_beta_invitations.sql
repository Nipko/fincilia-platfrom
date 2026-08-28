-- V0040: invitaciones de un solo uso para una beta realmente cerrada.
--
-- El runtime nunca ve la tabla ni puede fabricar invitaciones. Recibe solo
-- EXECUTE sobre una funcion que bloquea y consume un digest de alta entropia en
-- la misma transaccion que crea sujeto, firma y membresia.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

CREATE TABLE fincilia.beta_invitation (
  invitation_id uuid PRIMARY KEY,
  code_digest text NOT NULL UNIQUE
    CHECK (code_digest ~ '^sha256:[0-9a-f]{64}$'),
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  consumed_at timestamptz,
  consumed_by uuid REFERENCES fincilia.subject(subject_id),
  revoked_at timestamptz,
  CONSTRAINT ck_beta_invitation_expiry CHECK (expires_at > created_at),
  CONSTRAINT ck_beta_invitation_consumption CHECK (
    (consumed_at IS NULL) = (consumed_by IS NULL)
  ),
  CONSTRAINT ck_beta_invitation_terminal_state CHECK (
    NOT (consumed_at IS NOT NULL AND revoked_at IS NOT NULL)
  )
);

REVOKE ALL PRIVILEGES ON fincilia.beta_invitation FROM PUBLIC;
REVOKE ALL PRIVILEGES ON fincilia.beta_invitation FROM fincilia_app;

CREATE INDEX idx_beta_invitation_expiry
  ON fincilia.beta_invitation (expires_at)
  WHERE consumed_at IS NULL AND revoked_at IS NULL;

GRANT CREATE ON SCHEMA fincilia TO fincilia_identity;

ALTER TABLE fincilia.beta_invitation OWNER TO fincilia_identity;

CREATE FUNCTION fincilia.register_local_account_with_invite(
  p_invite_code_digest text,
  p_subject_id uuid,
  p_membership_id uuid,
  p_firm_id uuid,
  p_username text,
  p_identity_ref text,
  p_display_name text,
  p_firm_name text,
  p_algorithm text,
  p_iterations integer,
  p_salt text,
  p_secret_hash text
)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  v_invitation_id uuid;
BEGIN
  IF p_invite_code_digest !~ '^sha256:[0-9a-f]{64}$' THEN
    RAISE EXCEPTION 'closed beta registration is unavailable'
      USING ERRCODE = '22023';
  END IF;

  SELECT invitation_id INTO v_invitation_id
  FROM fincilia.beta_invitation
  WHERE code_digest = p_invite_code_digest
    AND consumed_at IS NULL
    AND revoked_at IS NULL
    AND expires_at > clock_timestamp()
  FOR UPDATE;

  IF v_invitation_id IS NULL THEN
    RAISE EXCEPTION 'closed beta registration is unavailable'
      USING ERRCODE = '22023';
  END IF;

  PERFORM fincilia.register_local_account(
    p_subject_id, p_membership_id, p_firm_id, p_username, p_identity_ref,
    p_display_name, p_firm_name, p_algorithm, p_iterations, p_salt,
    p_secret_hash
  );

  UPDATE fincilia.beta_invitation
  SET consumed_at = clock_timestamp(), consumed_by = p_subject_id
  WHERE invitation_id = v_invitation_id;
END
$function$;

ALTER FUNCTION fincilia.register_local_account_with_invite(
  text, uuid, uuid, uuid, text, text, text, text, text, integer, text, text
) OWNER TO fincilia_identity;

REVOKE CREATE ON SCHEMA fincilia FROM fincilia_identity;

SET LOCAL ROLE fincilia_identity;

REVOKE ALL PRIVILEGES ON FUNCTION fincilia.register_local_account_with_invite(
  text, uuid, uuid, uuid, text, text, text, text, text, integer, text, text
) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION fincilia.register_local_account_with_invite(
  text, uuid, uuid, uuid, text, text, text, text, text, integer, text, text
) TO fincilia_app;

COMMENT ON TABLE fincilia.beta_invitation IS
  'Digests de invitacion sintetica de un uso; nunca almacena el codigo.';
COMMENT ON FUNCTION fincilia.register_local_account_with_invite(
  text, uuid, uuid, uuid, text, text, text, text, text, integer, text, text
) IS 'Consume una invitacion valida y ejecuta el alta local en una transaccion.';

RESET ROLE;

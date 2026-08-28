-- V0039: registro autoservicio sintetico sin escritura directa de credenciales.
--
-- La funcion existe solo para el adaptador local de ADR-012. Su dominio
-- `@demo.local` y la configuracion fail-closed impiden presentarla como almacen
-- de identidad real. Subject, binding, credential, firm y membership nacen en
-- una unica sentencia/transaccion; company sigue en FNC-ONB-001.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

DO $roles$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fincilia_identity') THEN
    RAISE EXCEPTION USING
      ERRCODE = '28000',
      MESSAGE = 'V0039 requires role fincilia_identity',
      HINT = 'create the NOLOGIN role through the versioned database bootstrap';
  END IF;
END
$roles$;

GRANT USAGE ON SCHEMA fincilia TO fincilia_identity;
GRANT INSERT ON fincilia.subject, fincilia.identity_binding,
  fincilia.local_credential, fincilia.firm, fincilia.membership
TO fincilia_identity;

-- `firm` tiene RLS para lectura del runtime. La autoridad de identidad solo
-- puede insertar una firma activa; no recibe SELECT, UPDATE ni DELETE.
CREATE POLICY firm_synthetic_registration_insert ON fincilia.firm
  FOR INSERT
  TO fincilia_identity
  WITH CHECK (status = 'active');

GRANT CREATE ON SCHEMA fincilia TO fincilia_identity;

CREATE FUNCTION fincilia.register_local_account(
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
BEGIN
  IF p_username IS NULL
     OR p_username <> lower(btrim(p_username))
     OR p_username !~ '^[a-z0-9][a-z0-9._+-]{1,90}@demo[.]local$' THEN
    RAISE EXCEPTION 'local registration identity is unavailable'
      USING ERRCODE = '22023';
  END IF;

  IF p_identity_ref !~ '^sha256:[0-9a-f]{64}$'
     OR p_algorithm <> 'pbkdf2_sha256'
     OR p_iterations < 200000
     OR p_salt !~ '^[0-9a-f]{32}$'
     OR p_secret_hash !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION 'local registration credential is invalid'
      USING ERRCODE = '22023';
  END IF;

  IF length(btrim(p_display_name)) NOT BETWEEN 2 AND 200
     OR length(btrim(p_firm_name)) NOT BETWEEN 2 AND 300
     OR p_display_name ~ '[[:cntrl:]]'
     OR p_firm_name ~ '[[:cntrl:]]' THEN
    RAISE EXCEPTION 'local registration profile is invalid'
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
    p_subject_id, 'local', p_identity_ref
  );

  INSERT INTO fincilia.local_credential (
    subject_id, username, algorithm, iterations, salt, secret_hash
  ) VALUES (
    p_subject_id, p_username, p_algorithm, p_iterations, p_salt, p_secret_hash
  );

  INSERT INTO fincilia.firm (firm_id, legal_name, status)
  VALUES (p_firm_id, btrim(p_firm_name), 'active');

  INSERT INTO fincilia.membership (
    membership_id, subject_id, firm_id, firm_role, status
  ) VALUES (
    p_membership_id, p_subject_id, p_firm_id, 'owner', 'active'
  );
END
$function$;

ALTER FUNCTION fincilia.register_local_account(
  uuid, uuid, uuid, text, text, text, text, text, integer, text, text
) OWNER TO fincilia_identity;

REVOKE CREATE ON SCHEMA fincilia FROM fincilia_identity;

-- Tras ceder la propiedad el migrador, por NOINHERIT, ya no puede modificar el
-- ACL ni el comentario. Hacerlo sin SET ROLE aborta la migracion; un REVOKE que
-- solo avisa seria aun peor porque dejaria EXECUTE a PUBLIC. Actuamos como el
-- propietario minimo, concedemos exclusivamente al runtime y volvemos.
SET LOCAL ROLE fincilia_identity;

REVOKE ALL PRIVILEGES ON FUNCTION fincilia.register_local_account(
  uuid, uuid, uuid, text, text, text, text, text, integer, text, text
) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION fincilia.register_local_account(
  uuid, uuid, uuid, text, text, text, text, text, integer, text, text
) TO fincilia_app;

COMMENT ON FUNCTION fincilia.register_local_account(
  uuid, uuid, uuid, text, text, text, text, text, integer, text, text
) IS 'Alta atomica solo @demo.local; no habilita identidad ni datos reales.';

RESET ROLE;

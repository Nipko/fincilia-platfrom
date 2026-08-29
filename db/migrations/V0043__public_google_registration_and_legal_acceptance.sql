-- V0043: alta publica Google sin invitaciones y aceptacion legal versionada.
--
-- Cognito/Google prueba la identidad y el correo antes de que la API invoque
-- esta funcion. PostgreSQL recibe solamente referencias HMAC; ni correo ni sub
-- externos en claro cruzan esta frontera. El login no crea cuentas: solo el
-- recorrido explicito de registro puede ejecutar esta funcion.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

ALTER TABLE fincilia.identity_binding
  ADD COLUMN verified_email_ref text
  CHECK (
    verified_email_ref IS NULL
    OR verified_email_ref ~ '^hmac-sha256:v1:[0-9a-f]{64}$'
  );

CREATE UNIQUE INDEX uq_identity_binding_verified_email
  ON fincilia.identity_binding (verified_email_ref)
  WHERE verified_email_ref IS NOT NULL;

CREATE TABLE fincilia.legal_document_version (
  document_kind text NOT NULL
    CHECK (document_kind IN ('terms', 'privacy')),
  document_version text NOT NULL
    CHECK (document_version ~ '^[a-z]+-[0-9]{4}-[0-9]{2}-[0-9]{2}$'),
  published_at timestamptz NOT NULL,
  active_for_registration boolean NOT NULL DEFAULT false,
  PRIMARY KEY (document_kind, document_version)
);

CREATE UNIQUE INDEX uq_legal_document_active_registration
  ON fincilia.legal_document_version (document_kind)
  WHERE active_for_registration;

INSERT INTO fincilia.legal_document_version (
  document_kind, document_version, published_at, active_for_registration
) VALUES
  ('terms', 'terms-2026-08-29', '2026-08-29T00:00:00Z', true),
  ('privacy', 'privacy-2026-08-29', '2026-08-29T00:00:00Z', true);

CREATE TABLE fincilia.subject_legal_acceptance (
  acceptance_id uuid PRIMARY KEY,
  subject_id uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  document_kind text NOT NULL,
  document_version text NOT NULL,
  acceptance_channel text NOT NULL
    CHECK (acceptance_channel = 'google_oidc_registration'),
  accepted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  FOREIGN KEY (document_kind, document_version)
    REFERENCES fincilia.legal_document_version(document_kind, document_version),
  UNIQUE (subject_id, document_kind, document_version)
);

REVOKE ALL PRIVILEGES ON fincilia.legal_document_version FROM PUBLIC;
REVOKE ALL PRIVILEGES ON fincilia.subject_legal_acceptance FROM PUBLIC;
REVOKE ALL PRIVILEGES ON fincilia.legal_document_version FROM fincilia_app;
REVOKE ALL PRIVILEGES ON fincilia.subject_legal_acceptance FROM fincilia_app;

GRANT CREATE ON SCHEMA fincilia TO fincilia_identity;
ALTER TABLE fincilia.legal_document_version OWNER TO fincilia_identity;
ALTER TABLE fincilia.subject_legal_acceptance OWNER TO fincilia_identity;

CREATE FUNCTION fincilia.register_external_account_public(
  p_verified_email_ref text,
  p_subject_id uuid,
  p_membership_id uuid,
  p_firm_id uuid,
  p_issuer text,
  p_external_subject_ref text,
  p_display_name text,
  p_firm_name text,
  p_terms_version text,
  p_privacy_version text
)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $function$
BEGIN
  IF p_verified_email_ref !~ '^hmac-sha256:v1:[0-9a-f]{64}$'
     OR p_external_subject_ref !~ '^hmac-sha256:v1:[0-9a-f]{64}$'
     OR length(p_issuer) NOT BETWEEN 12 AND 508
     OR p_issuer !~ '^https://[^[:space:][:cntrl:]]+$' THEN
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

  IF NOT EXISTS (
       SELECT 1 FROM fincilia.legal_document_version
       WHERE document_kind = 'terms'
         AND document_version = p_terms_version
         AND active_for_registration
     ) OR NOT EXISTS (
       SELECT 1 FROM fincilia.legal_document_version
       WHERE document_kind = 'privacy'
         AND document_version = p_privacy_version
         AND active_for_registration
     ) THEN
    RAISE EXCEPTION 'legal acceptance version is not current'
      USING ERRCODE = '22023';
  END IF;

  INSERT INTO fincilia.subject (
    subject_id, subject_kind, display_name, status
  ) VALUES (
    p_subject_id, 'person', btrim(p_display_name), 'active'
  );

  INSERT INTO fincilia.identity_binding (
    subject_id, issuer, external_subject_ref, verified_email_ref
  ) VALUES (
    p_subject_id, p_issuer, p_external_subject_ref, p_verified_email_ref
  );

  INSERT INTO fincilia.firm (firm_id, legal_name, status)
  VALUES (p_firm_id, btrim(p_firm_name), 'active');

  INSERT INTO fincilia.membership (
    membership_id, subject_id, firm_id, firm_role, status
  ) VALUES (
    p_membership_id, p_subject_id, p_firm_id, 'owner', 'active'
  );

  INSERT INTO fincilia.subject_legal_acceptance (
    acceptance_id, subject_id, document_kind, document_version,
    acceptance_channel
  ) VALUES
    (gen_random_uuid(), p_subject_id, 'terms', p_terms_version,
     'google_oidc_registration'),
    (gen_random_uuid(), p_subject_id, 'privacy', p_privacy_version,
     'google_oidc_registration');
END
$function$;

ALTER FUNCTION fincilia.register_external_account_public(
  text, uuid, uuid, uuid, text, text, text, text, text, text
) OWNER TO fincilia_identity;

REVOKE CREATE ON SCHEMA fincilia FROM fincilia_identity;

SET LOCAL ROLE fincilia_identity;

REVOKE ALL PRIVILEGES ON FUNCTION fincilia.register_external_account_public(
  text, uuid, uuid, uuid, text, text, text, text, text, text
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.register_external_account_public(
  text, uuid, uuid, uuid, text, text, text, text, text, text
) TO fincilia_app;

-- La ruta antigua permanece como evidencia historica de las migraciones, pero
-- deja de ser una superficie disponible para el runtime definitivo.
REVOKE EXECUTE ON FUNCTION fincilia.register_external_account_with_invite(
  text, text, uuid, uuid, uuid, text, text, text, text
) FROM fincilia_app;

COMMENT ON TABLE fincilia.legal_document_version IS
  'Versiones legales publicadas que el alta puede aceptar; una activa por clase.';
COMMENT ON TABLE fincilia.subject_legal_acceptance IS
  'Evidencia versionada y minimizada de aceptacion legal por identidad interna.';
COMMENT ON FUNCTION fincilia.register_external_account_public(
  text, uuid, uuid, uuid, text, text, text, text, text, text
) IS 'Alta publica Google atomica: sujeto, binding HMAC, firma, owner y aceptaciones.';

RESET ROLE;

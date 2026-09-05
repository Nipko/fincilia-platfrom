-- FNC-NTF-002: despacho durable de correo, destino cifrado y feedback minimizado.
-- Ninguna direccion de correo existe en claro en PostgreSQL. El worker recibe
-- ciphertext y lo descifra con KMS solo durante el envio. Las funciones son
-- SECURITY DEFINER bajo una autoridad NOLOGIN sin DDL.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

DO $roles$
DECLARE
  v_missing text[] := ARRAY[]::text[];
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = 'fincilia_notification_worker'
  ) THEN
    v_missing := v_missing || 'fincilia_notification_worker';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = 'fincilia_notification_dispatch'
  ) THEN
    v_missing := v_missing || 'fincilia_notification_dispatch';
  END IF;
  IF array_length(v_missing, 1) IS NOT NULL THEN
    RAISE EXCEPTION USING
      ERRCODE = '28000',
      MESSAGE = format('V0059 requires roles %s', array_to_string(v_missing, ', ')),
      HINT = 'provision the roles before applying schema migrations';
  END IF;
END
$roles$;

GRANT USAGE ON SCHEMA fincilia
  TO fincilia_notification_worker, fincilia_notification_dispatch;

CREATE TABLE fincilia.notification_destination (
  subject_id uuid PRIMARY KEY REFERENCES fincilia.subject(subject_id)
    ON DELETE RESTRICT,
  address_ref text NOT NULL UNIQUE
    CHECK (address_ref ~ '^hmac-sha256:v1:[0-9a-f]{64}$'),
  encrypted_address bytea NOT NULL
    CHECK (octet_length(encrypted_address) BETWEEN 32 AND 6144),
  kms_key_ref text NOT NULL CHECK (
    kms_key_ref ~ '^arn:aws:kms:[a-z]{2}-[a-z]+-[0-9]:[0-9]{12}:key/[0-9a-f-]{36}$'),
  encryption_context_version text NOT NULL
    DEFAULT 'notification-email-v1'
    CHECK (encryption_context_version = 'notification-email-v1'),
  status text NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'suppressed')),
  suppression_reason text CHECK (
    suppression_reason IS NULL
    OR suppression_reason IN ('hard_bounce', 'provider_complaint')),
  verified_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT ck_notification_destination_state CHECK (
    (status = 'active' AND suppression_reason IS NULL)
    OR (status = 'suppressed' AND suppression_reason IS NOT NULL)
  )
);

REVOKE ALL PRIVILEGES ON fincilia.notification_destination FROM PUBLIC;
REVOKE ALL PRIVILEGES ON fincilia.notification_destination
  FROM fincilia_app, fincilia_notification_worker;
GRANT SELECT, INSERT, UPDATE ON fincilia.notification_destination
  TO fincilia_identity;
GRANT SELECT, UPDATE ON fincilia.notification_destination
  TO fincilia_notification_dispatch;

ALTER TABLE fincilia.notification_delivery
  DROP CONSTRAINT notification_delivery_status_check,
  DROP CONSTRAINT notification_delivery_suppression_reason_check,
  DROP CONSTRAINT ck_notification_provider_state;

ALTER TABLE fincilia.notification_delivery
  ADD CONSTRAINT ck_notification_delivery_status CHECK (
    status IN ('queued', 'sending', 'sent', 'delivered', 'failed',
               'uncertain', 'suppressed')),
  ADD CONSTRAINT ck_notification_delivery_suppression_reason CHECK (
    suppression_reason IS NULL OR suppression_reason IN (
      'user_opt_out', 'adapter_unconfigured', 'destination_unavailable',
      'hard_bounce', 'provider_complaint')),
  ADD COLUMN lease_token uuid,
  ADD COLUMN lease_expires_at timestamptz,
  ADD COLUMN claimed_by text CHECK (
    claimed_by IS NULL OR length(claimed_by) BETWEEN 3 AND 100),
  ADD COLUMN max_attempts integer NOT NULL DEFAULT 5
    CHECK (max_attempts BETWEEN 1 AND 8),
  ADD COLUMN sent_at timestamptz,
  ADD COLUMN delivered_at timestamptz,
  ADD CONSTRAINT ck_notification_delivery_lease CHECK (
    (status = 'sending' AND lease_token IS NOT NULL
      AND lease_expires_at IS NOT NULL AND claimed_by IS NOT NULL)
    OR (status <> 'sending' AND lease_token IS NULL
      AND lease_expires_at IS NULL AND claimed_by IS NULL)),
  ADD CONSTRAINT ck_notification_provider_state CHECK (
    (status IN ('sent', 'delivered') AND provider_message_ref IS NOT NULL)
    OR (status IN ('queued', 'sending', 'failed', 'uncertain')
      AND provider_message_ref IS NULL)
    OR (status = 'suppressed' AND (
      (suppression_reason IN ('hard_bounce', 'provider_complaint')
        AND provider_message_ref IS NOT NULL)
      OR (suppression_reason NOT IN ('hard_bounce', 'provider_complaint')
        AND provider_message_ref IS NULL)))
  ),
  ADD CONSTRAINT ck_notification_delivery_moments CHECK (
    (sent_at IS NULL OR status IN ('sent', 'delivered', 'suppressed'))
    AND (delivered_at IS NULL OR (
      status IN ('delivered', 'suppressed') AND sent_at IS NOT NULL))
  );

CREATE INDEX idx_notification_delivery_dispatch
  ON fincilia.notification_delivery (available_at, created_at, delivery_id)
  WHERE status = 'queued';

CREATE TABLE fincilia.notification_delivery_attempt (
  attempt_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  delivery_id uuid NOT NULL REFERENCES fincilia.notification_delivery(delivery_id)
    ON DELETE RESTRICT,
  company_id uuid NOT NULL REFERENCES fincilia.company(company_id)
    ON DELETE RESTRICT,
  attempt_number integer NOT NULL CHECK (attempt_number BETWEEN 1 AND 8),
  lease_token uuid NOT NULL,
  worker text NOT NULL CHECK (length(worker) BETWEEN 3 AND 100),
  outcome text NOT NULL DEFAULT 'sending'
    CHECK (outcome IN ('sending', 'sent', 'retryable', 'fatal', 'uncertain')),
  reason_code text CHECK (
    reason_code IS NULL OR reason_code ~ '^[a-z][a-z0-9_]{2,63}$'),
  started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  finished_at timestamptz,
  CONSTRAINT uq_notification_attempt UNIQUE (delivery_id, attempt_number),
  CONSTRAINT uq_notification_attempt_lease UNIQUE (lease_token),
  CONSTRAINT ck_notification_attempt_moments CHECK (
    (outcome = 'sending' AND finished_at IS NULL)
    OR (outcome <> 'sending' AND finished_at IS NOT NULL
      AND finished_at >= started_at))
);

ALTER TABLE fincilia.notification_delivery_attempt ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.notification_delivery_attempt FORCE ROW LEVEL SECURITY;
CREATE POLICY notification_attempt_dispatch
  ON fincilia.notification_delivery_attempt
  TO fincilia_notification_dispatch
  USING (true) WITH CHECK (true);

CREATE TABLE fincilia.notification_feedback_event (
  feedback_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES fincilia.company(company_id)
    ON DELETE RESTRICT,
  delivery_id uuid NOT NULL REFERENCES fincilia.notification_delivery(delivery_id)
    ON DELETE RESTRICT,
  provider_event_digest text NOT NULL UNIQUE
    CHECK (provider_event_digest ~ '^[0-9a-f]{64}$'),
  provider_message_ref text NOT NULL
    CHECK (provider_message_ref ~ '^sha256:[0-9a-f]{64}$'),
  event_type text NOT NULL
    CHECK (event_type IN ('delivered', 'hard_bounce', 'complaint')),
  recorded_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

ALTER TABLE fincilia.notification_feedback_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.notification_feedback_event FORCE ROW LEVEL SECURITY;
CREATE POLICY notification_feedback_dispatch
  ON fincilia.notification_feedback_event
  TO fincilia_notification_dispatch
  USING (true) WITH CHECK (true);

GRANT SELECT ON fincilia.notification_preference,
  fincilia.notification_intent, fincilia.notification_delivery
  TO fincilia_notification_dispatch;
GRANT UPDATE ON fincilia.notification_delivery
  TO fincilia_notification_dispatch;
GRANT SELECT, INSERT, UPDATE ON fincilia.notification_delivery_attempt
  TO fincilia_notification_dispatch;
GRANT SELECT, INSERT ON fincilia.notification_feedback_event
  TO fincilia_notification_dispatch;

CREATE POLICY notification_preference_dispatch
  ON fincilia.notification_preference FOR SELECT
  TO fincilia_notification_dispatch USING (true);
CREATE POLICY notification_intent_dispatch
  ON fincilia.notification_intent FOR SELECT
  TO fincilia_notification_dispatch USING (true);
CREATE POLICY notification_delivery_dispatch
  ON fincilia.notification_delivery
  TO fincilia_notification_dispatch USING (true) WITH CHECK (true);

GRANT CREATE ON SCHEMA fincilia TO fincilia_identity;

CREATE FUNCTION fincilia.upsert_verified_notification_destination(
  p_subject_id uuid,
  p_address_ref text,
  p_encrypted_address bytea,
  p_kms_key_ref text
)
RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $function$
BEGIN
  IF p_subject_id IS NULL
     OR p_subject_id::text <> current_setting('fincilia.subject_id', true)
     OR p_address_ref !~ '^hmac-sha256:v1:[0-9a-f]{64}$'
     OR octet_length(p_encrypted_address) NOT BETWEEN 32 AND 6144
     OR p_kms_key_ref !~
       '^arn:aws:kms:[a-z]{2}-[a-z]+-[0-9]:[0-9]{12}:key/[0-9a-f-]{36}$' THEN
    RAISE invalid_parameter_value USING MESSAGE = 'notification destination rejected';
  END IF;

  INSERT INTO fincilia.notification_destination (
    subject_id, address_ref, encrypted_address, kms_key_ref,
    status, suppression_reason, verified_at, updated_at
  ) VALUES (
    p_subject_id, p_address_ref, p_encrypted_address, p_kms_key_ref,
    'active', NULL, clock_timestamp(), clock_timestamp()
  )
  ON CONFLICT (subject_id) DO UPDATE SET
    address_ref = EXCLUDED.address_ref,
    encrypted_address = EXCLUDED.encrypted_address,
    kms_key_ref = EXCLUDED.kms_key_ref,
    status = 'active',
    suppression_reason = NULL,
    verified_at = clock_timestamp(),
    updated_at = clock_timestamp();
END
$function$;

CREATE FUNCTION fincilia.my_notification_destination_state(p_subject_id uuid)
RETURNS text
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  v_state text;
BEGIN
  IF p_subject_id IS NULL
     OR p_subject_id::text <> current_setting('fincilia.subject_id', true) THEN
    RAISE insufficient_privilege USING MESSAGE = 'notification destination denied';
  END IF;
  SELECT status INTO v_state
    FROM fincilia.notification_destination
   WHERE subject_id = p_subject_id;
  RETURN COALESCE(v_state, 'unavailable');
END
$function$;

REVOKE ALL PRIVILEGES ON FUNCTION
  fincilia.upsert_verified_notification_destination(uuid, text, bytea, text)
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
  fincilia.upsert_verified_notification_destination(uuid, text, bytea, text)
  TO fincilia_app;
REVOKE ALL PRIVILEGES ON FUNCTION
  fincilia.my_notification_destination_state(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
  fincilia.my_notification_destination_state(uuid) TO fincilia_app;

ALTER FUNCTION fincilia.upsert_verified_notification_destination(
  uuid, text, bytea, text
) OWNER TO fincilia_identity;
ALTER FUNCTION fincilia.my_notification_destination_state(uuid)
  OWNER TO fincilia_identity;
REVOKE CREATE ON SCHEMA fincilia FROM fincilia_identity;

GRANT CREATE ON SCHEMA fincilia TO fincilia_notification_dispatch;

CREATE FUNCTION fincilia.claim_notification_delivery(
  p_worker text,
  p_lease_seconds integer DEFAULT 60
)
RETURNS TABLE(
  delivery_id uuid,
  company_id uuid,
  subject_id uuid,
  template_code text,
  render_context jsonb,
  locale text,
  idempotency_key text,
  encrypted_address bytea,
  address_ref text,
  kms_key_ref text,
  lease_token uuid,
  attempt_number integer
)
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  v_delivery fincilia.notification_delivery%ROWTYPE;
  v_intent fincilia.notification_intent%ROWTYPE;
  v_preference fincilia.notification_preference%ROWTYPE;
  v_destination fincilia.notification_destination%ROWTYPE;
  v_lease uuid := gen_random_uuid();
BEGIN
  IF p_worker IS NULL OR length(p_worker) NOT BETWEEN 3 AND 100
     OR p_lease_seconds NOT BETWEEN 15 AND 300 THEN
    RAISE invalid_parameter_value USING MESSAGE = 'notification claim rejected';
  END IF;

  -- Recuperar un worker muerto antes de reclamar otra fila. El lease es el
  -- fencing token: una finalizacion tardia del proceso anterior devolvera
  -- stale_lease y no podra pisar este estado.
  UPDATE fincilia.notification_delivery_attempt AS attempt
     SET outcome = 'retryable', reason_code = 'lease_expired',
         finished_at = clock_timestamp()
    FROM fincilia.notification_delivery AS delivery
   WHERE delivery.delivery_id = attempt.delivery_id
     AND delivery.status = 'sending'
     AND delivery.lease_expires_at <= clock_timestamp()
     AND attempt.lease_token = delivery.lease_token
     AND attempt.outcome = 'sending';

  UPDATE fincilia.notification_delivery AS delivery
     SET status = CASE WHEN delivery.attempt_count < delivery.max_attempts
                       THEN 'queued' ELSE 'failed' END,
         last_error_code = 'lease_expired',
         available_at = clock_timestamp(),
         lease_token = NULL, lease_expires_at = NULL, claimed_by = NULL,
         updated_at = clock_timestamp()
   WHERE delivery.status = 'sending'
     AND delivery.lease_expires_at <= clock_timestamp();

  SELECT delivery.* INTO v_delivery
    FROM fincilia.notification_delivery AS delivery
   WHERE delivery.status = 'queued'
     AND delivery.available_at <= statement_timestamp()
   ORDER BY delivery.available_at, delivery.created_at, delivery.delivery_id
   FOR UPDATE SKIP LOCKED
   LIMIT 1;
  IF NOT FOUND THEN
    RETURN;
  END IF;

  SELECT intent.* INTO STRICT v_intent
    FROM fincilia.notification_intent AS intent
   WHERE intent.intent_id = v_delivery.intent_id;
  SELECT preference.* INTO v_preference
    FROM fincilia.notification_preference AS preference
   WHERE preference.company_id = v_delivery.company_id
     AND preference.subject_id = v_delivery.subject_id
     AND preference.channel = 'email'
     AND preference.purpose_code = 'operational_reminder';
  SELECT destination.* INTO v_destination
    FROM fincilia.notification_destination AS destination
   WHERE destination.subject_id = v_delivery.subject_id;

  IF v_preference.preference_id IS NULL OR NOT v_preference.enabled THEN
    UPDATE fincilia.notification_delivery
       SET status = 'suppressed', suppression_reason = 'user_opt_out',
           updated_at = clock_timestamp()
     WHERE notification_delivery.delivery_id = v_delivery.delivery_id;
    RETURN;
  END IF;
  IF v_destination.subject_id IS NULL OR v_destination.status <> 'active' THEN
    UPDATE fincilia.notification_delivery
       SET status = 'suppressed', suppression_reason = 'destination_unavailable',
           updated_at = clock_timestamp()
     WHERE notification_delivery.delivery_id = v_delivery.delivery_id;
    RETURN;
  END IF;

  UPDATE fincilia.notification_delivery
     SET status = 'sending', suppression_reason = NULL,
         lease_token = v_lease,
         lease_expires_at = clock_timestamp() + make_interval(secs => p_lease_seconds),
         claimed_by = p_worker,
         attempt_count = attempt_count + 1,
         updated_at = clock_timestamp()
   WHERE notification_delivery.delivery_id = v_delivery.delivery_id;

  INSERT INTO fincilia.notification_delivery_attempt (
    delivery_id, company_id, attempt_number, lease_token, worker
  ) VALUES (
    v_delivery.delivery_id, v_delivery.company_id,
    v_delivery.attempt_count + 1, v_lease, p_worker
  );

  RETURN QUERY SELECT
    v_delivery.delivery_id, v_delivery.company_id, v_delivery.subject_id,
    v_intent.template_code, v_intent.render_context, v_preference.locale,
    v_delivery.idempotency_key, v_destination.encrypted_address,
    v_destination.address_ref, v_destination.kms_key_ref,
    v_lease, v_delivery.attempt_count + 1;
END
$function$;

CREATE FUNCTION fincilia.finish_notification_delivery(
  p_delivery_id uuid,
  p_lease_token uuid,
  p_outcome text,
  p_provider_message_ref text DEFAULT NULL,
  p_reason_code text DEFAULT NULL
)
RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  v_delivery fincilia.notification_delivery%ROWTYPE;
  v_status text;
BEGIN
  IF p_outcome NOT IN ('sent', 'retryable', 'fatal', 'uncertain')
     OR (p_reason_code IS NOT NULL
       AND p_reason_code !~ '^[a-z][a-z0-9_]{2,63}$')
     OR (p_outcome = 'sent') <> (p_provider_message_ref IS NOT NULL)
     OR (p_outcome <> 'sent' AND p_reason_code IS NULL)
     OR (p_provider_message_ref IS NOT NULL
       AND p_provider_message_ref !~ '^sha256:[0-9a-f]{64}$') THEN
    RAISE invalid_parameter_value USING MESSAGE = 'notification outcome rejected';
  END IF;

  SELECT delivery.* INTO v_delivery
    FROM fincilia.notification_delivery AS delivery
   WHERE delivery.delivery_id = p_delivery_id
     AND delivery.status = 'sending'
     AND delivery.lease_token = p_lease_token
   FOR UPDATE;
  IF NOT FOUND THEN
    RETURN 'stale_lease';
  END IF;

  UPDATE fincilia.notification_delivery_attempt
     SET outcome = p_outcome, reason_code = p_reason_code,
         finished_at = clock_timestamp()
   WHERE delivery_id = p_delivery_id AND lease_token = p_lease_token
     AND outcome = 'sending';
  IF NOT FOUND THEN
    RAISE integrity_constraint_violation
      USING MESSAGE = 'notification attempt is missing';
  END IF;

  IF p_outcome = 'sent' THEN
    v_status := 'sent';
    UPDATE fincilia.notification_delivery
       SET status = 'sent', provider_message_ref = p_provider_message_ref,
           sent_at = clock_timestamp(), last_error_code = NULL,
           lease_token = NULL, lease_expires_at = NULL, claimed_by = NULL,
           updated_at = clock_timestamp()
     WHERE notification_delivery.delivery_id = p_delivery_id;
  ELSIF p_outcome = 'retryable' AND v_delivery.attempt_count < v_delivery.max_attempts THEN
    v_status := 'queued';
    UPDATE fincilia.notification_delivery
       SET status = 'queued', last_error_code = p_reason_code,
           available_at = clock_timestamp() + CASE v_delivery.attempt_count
             WHEN 1 THEN interval '1 minute'
             WHEN 2 THEN interval '5 minutes'
             WHEN 3 THEN interval '30 minutes'
             ELSE interval '2 hours' END,
           lease_token = NULL, lease_expires_at = NULL, claimed_by = NULL,
           updated_at = clock_timestamp()
     WHERE notification_delivery.delivery_id = p_delivery_id;
  ELSIF p_outcome = 'uncertain' THEN
    v_status := 'uncertain';
    UPDATE fincilia.notification_delivery
       SET status = 'uncertain', last_error_code = p_reason_code,
           lease_token = NULL, lease_expires_at = NULL, claimed_by = NULL,
           updated_at = clock_timestamp()
     WHERE notification_delivery.delivery_id = p_delivery_id;
  ELSE
    v_status := 'failed';
    UPDATE fincilia.notification_delivery
       SET status = 'failed', last_error_code = p_reason_code,
           lease_token = NULL, lease_expires_at = NULL, claimed_by = NULL,
           updated_at = clock_timestamp()
     WHERE notification_delivery.delivery_id = p_delivery_id;
  END IF;
  RETURN v_status;
END
$function$;

CREATE FUNCTION fincilia.record_notification_feedback(
  p_provider_event_digest text,
  p_provider_message_ref text,
  p_event_type text
)
RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  v_delivery fincilia.notification_delivery%ROWTYPE;
BEGIN
  IF p_provider_event_digest !~ '^[0-9a-f]{64}$'
     OR p_provider_message_ref !~ '^sha256:[0-9a-f]{64}$'
     OR p_event_type NOT IN ('delivered', 'hard_bounce', 'complaint') THEN
    RAISE invalid_parameter_value USING MESSAGE = 'notification feedback rejected';
  END IF;

  IF EXISTS (
    SELECT 1 FROM fincilia.notification_feedback_event
     WHERE provider_event_digest = p_provider_event_digest
  ) THEN
    RETURN 'replayed';
  END IF;

  SELECT delivery.* INTO v_delivery
    FROM fincilia.notification_delivery AS delivery
   WHERE delivery.provider_message_ref = p_provider_message_ref
   FOR UPDATE;
  IF NOT FOUND THEN
    RETURN 'unknown_delivery';
  END IF;

  INSERT INTO fincilia.notification_feedback_event (
    company_id, delivery_id, provider_event_digest,
    provider_message_ref, event_type
  ) VALUES (
    v_delivery.company_id, v_delivery.delivery_id, p_provider_event_digest,
    p_provider_message_ref, p_event_type
  );

  IF p_event_type = 'delivered' THEN
    UPDATE fincilia.notification_delivery
       SET status = 'delivered', delivered_at = clock_timestamp(),
           updated_at = clock_timestamp()
     WHERE notification_delivery.delivery_id = v_delivery.delivery_id
       AND notification_delivery.status = 'sent';
  ELSE
    UPDATE fincilia.notification_delivery
       SET status = 'suppressed',
           suppression_reason = CASE p_event_type
             WHEN 'hard_bounce' THEN 'hard_bounce'
             ELSE 'provider_complaint' END,
           updated_at = clock_timestamp()
     WHERE notification_delivery.delivery_id = v_delivery.delivery_id
       AND notification_delivery.status IN ('sent', 'delivered');
    UPDATE fincilia.notification_destination
       SET status = 'suppressed',
           suppression_reason = CASE p_event_type
             WHEN 'hard_bounce' THEN 'hard_bounce'
             ELSE 'provider_complaint' END,
           updated_at = clock_timestamp()
     WHERE notification_destination.subject_id = v_delivery.subject_id;
  END IF;
  RETURN p_event_type;
END
$function$;

REVOKE ALL PRIVILEGES ON FUNCTION
  fincilia.claim_notification_delivery(text, integer) FROM PUBLIC;
REVOKE ALL PRIVILEGES ON FUNCTION
  fincilia.finish_notification_delivery(uuid, uuid, text, text, text) FROM PUBLIC;
REVOKE ALL PRIVILEGES ON FUNCTION
  fincilia.record_notification_feedback(text, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
  fincilia.claim_notification_delivery(text, integer)
  TO fincilia_notification_worker;
GRANT EXECUTE ON FUNCTION
  fincilia.finish_notification_delivery(uuid, uuid, text, text, text)
  TO fincilia_notification_worker;
GRANT EXECUTE ON FUNCTION
  fincilia.record_notification_feedback(text, text, text)
  TO fincilia_notification_worker;

COMMENT ON FUNCTION fincilia.claim_notification_delivery(text, integer) IS
  'Claim global de correo con lease; excepcion RLS solo mediante rol NOLOGIN.';

ALTER FUNCTION fincilia.claim_notification_delivery(text, integer)
  OWNER TO fincilia_notification_dispatch;
ALTER FUNCTION fincilia.finish_notification_delivery(
  uuid, uuid, text, text, text
) OWNER TO fincilia_notification_dispatch;
ALTER FUNCTION fincilia.record_notification_feedback(text, text, text)
  OWNER TO fincilia_notification_dispatch;
REVOKE CREATE ON SCHEMA fincilia FROM fincilia_notification_dispatch;

REVOKE ALL PRIVILEGES ON fincilia.notification_delivery_attempt,
  fincilia.notification_feedback_event FROM PUBLIC, fincilia_app,
  fincilia_notification_worker;

COMMENT ON TABLE fincilia.notification_destination IS
  'Destino global cifrado por KMS; no contiene direcciones en claro.';

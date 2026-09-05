-- FNC-NTF-002: frontera at-most-once para proveedores sin idempotencia.
-- Antes de tocar SES el intento se arma de forma durable como uncertain. Si el
-- proceso cae despues del envio, el claim nunca se recicla ni duplica el correo.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

GRANT CREATE ON SCHEMA fincilia TO fincilia_notification_dispatch;

CREATE FUNCTION fincilia.arm_notification_delivery(
  p_delivery_id uuid,
  p_lease_token uuid
)
RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $function$
BEGIN
  IF p_delivery_id IS NULL OR p_lease_token IS NULL THEN
    RAISE invalid_parameter_value USING MESSAGE = 'notification arm rejected';
  END IF;

  PERFORM 1
    FROM fincilia.notification_delivery AS delivery
   WHERE delivery.delivery_id = p_delivery_id
     AND delivery.status = 'sending'
     AND delivery.lease_token = p_lease_token
   FOR UPDATE;
  IF NOT FOUND THEN
    RETURN 'stale_lease';
  END IF;

  UPDATE fincilia.notification_delivery_attempt
     SET outcome = 'uncertain', reason_code = 'provider_attempt_started',
         finished_at = clock_timestamp()
   WHERE delivery_id = p_delivery_id
     AND lease_token = p_lease_token
     AND outcome = 'sending';
  IF NOT FOUND THEN
    RAISE integrity_constraint_violation
      USING MESSAGE = 'notification attempt is missing';
  END IF;

  UPDATE fincilia.notification_delivery
     SET status = 'uncertain', last_error_code = 'provider_attempt_started',
         lease_token = NULL, lease_expires_at = NULL, claimed_by = NULL,
         updated_at = clock_timestamp()
   WHERE delivery_id = p_delivery_id;
  RETURN 'armed';
END
$function$;

CREATE FUNCTION fincilia.settle_armed_notification_delivery(
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
    RAISE invalid_parameter_value USING MESSAGE = 'notification settlement rejected';
  END IF;

  SELECT delivery.* INTO v_delivery
    FROM fincilia.notification_delivery AS delivery
   WHERE delivery.delivery_id = p_delivery_id
     AND delivery.status = 'uncertain'
     AND delivery.last_error_code = 'provider_attempt_started'
   FOR UPDATE;
  IF NOT FOUND OR NOT EXISTS (
    SELECT 1 FROM fincilia.notification_delivery_attempt AS attempt
     WHERE attempt.delivery_id = p_delivery_id
       AND attempt.lease_token = p_lease_token
       AND attempt.outcome = 'uncertain'
       AND attempt.reason_code = 'provider_attempt_started'
  ) THEN
    RETURN 'stale_lease';
  END IF;

  UPDATE fincilia.notification_delivery_attempt
     SET outcome = p_outcome, reason_code = p_reason_code,
         finished_at = clock_timestamp()
   WHERE delivery_id = p_delivery_id AND lease_token = p_lease_token;

  IF p_outcome = 'sent' THEN
    v_status := 'sent';
    UPDATE fincilia.notification_delivery
       SET status = 'sent', provider_message_ref = p_provider_message_ref,
           sent_at = clock_timestamp(), last_error_code = NULL,
           updated_at = clock_timestamp()
     WHERE delivery_id = p_delivery_id;
  ELSIF p_outcome = 'retryable' AND v_delivery.attempt_count < v_delivery.max_attempts THEN
    v_status := 'queued';
    UPDATE fincilia.notification_delivery
       SET status = 'queued', last_error_code = p_reason_code,
           available_at = clock_timestamp() + CASE v_delivery.attempt_count
             WHEN 1 THEN interval '1 minute'
             WHEN 2 THEN interval '5 minutes'
             WHEN 3 THEN interval '30 minutes'
             ELSE interval '2 hours' END,
           updated_at = clock_timestamp()
     WHERE delivery_id = p_delivery_id;
  ELSIF p_outcome = 'uncertain' THEN
    v_status := 'uncertain';
    UPDATE fincilia.notification_delivery
       SET last_error_code = p_reason_code, updated_at = clock_timestamp()
     WHERE delivery_id = p_delivery_id;
  ELSE
    v_status := 'failed';
    UPDATE fincilia.notification_delivery
       SET status = 'failed', last_error_code = p_reason_code,
           updated_at = clock_timestamp()
     WHERE delivery_id = p_delivery_id;
  END IF;
  RETURN v_status;
END
$function$;

REVOKE ALL PRIVILEGES ON FUNCTION
  fincilia.arm_notification_delivery(uuid, uuid) FROM PUBLIC;
REVOKE ALL PRIVILEGES ON FUNCTION
  fincilia.settle_armed_notification_delivery(uuid, uuid, text, text, text)
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.arm_notification_delivery(uuid, uuid)
  TO fincilia_notification_worker;
GRANT EXECUTE ON FUNCTION
  fincilia.settle_armed_notification_delivery(uuid, uuid, text, text, text)
  TO fincilia_notification_worker;

COMMENT ON FUNCTION fincilia.arm_notification_delivery(uuid, uuid) IS
  'Frontera durable anterior a SES; un crash posterior permanece uncertain.';
COMMENT ON FUNCTION fincilia.settle_armed_notification_delivery(
  uuid, uuid, text, text, text
) IS 'Asienta solo el intento armado exacto mediante su fencing token.';

ALTER FUNCTION fincilia.arm_notification_delivery(uuid, uuid)
  OWNER TO fincilia_notification_dispatch;
ALTER FUNCTION fincilia.settle_armed_notification_delivery(
  uuid, uuid, text, text, text
) OWNER TO fincilia_notification_dispatch;
REVOKE CREATE ON SCHEMA fincilia FROM fincilia_notification_dispatch;

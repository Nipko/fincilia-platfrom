-- FNC-BIL-002: serializa el estado Stripe por firma y distingue un replay
-- exacto de una colision de evidencia. V0064/V0065 permanecen inmutables.

-- Las funciones ya pertenecen a la autoridad NOLOGIN desde V0064. Se entra a
-- ese rol de forma explicita para reemplazarlas y administrar su ACL; NOINHERIT
-- impide suponer que la membresia del migrador equivale a ser el propietario.
GRANT CREATE ON SCHEMA fincilia TO fincilia_billing_dispatch;
SET LOCAL ROLE fincilia_billing_dispatch;

CREATE OR REPLACE FUNCTION fincilia.record_stripe_webhook(
  p_event_id text, p_event_type text, p_created_at timestamptz,
  p_event_digest text, p_payload_digest text, p_outcome text)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $$
DECLARE
  v_existing fincilia.billing_webhook_inbox%ROWTYPE;
BEGIN
  IF p_event_id !~ '^evt_[A-Za-z0-9]{8,}$'
     OR length(p_event_type) NOT BETWEEN 3 AND 120
     OR p_event_digest !~ '^[0-9a-f]{64}$'
     OR p_payload_digest !~ '^[0-9a-f]{64}$'
     OR p_outcome NOT IN ('processing', 'ignored') THEN
    RAISE EXCEPTION 'billing-webhook-invalid' USING ERRCODE = '22023';
  END IF;
  INSERT INTO fincilia.billing_webhook_inbox (
    provider_code, provider_event_digest, payload_digest, signature_state,
    provider_event_id, event_type, provider_created_at, processing_state,
    processed_at, outcome_code)
  VALUES ('stripe', p_event_digest, p_payload_digest, 'verified', p_event_id,
    p_event_type, p_created_at, p_outcome,
    CASE WHEN p_outcome = 'ignored' THEN now() ELSE NULL END,
    CASE WHEN p_outcome = 'ignored' THEN 'event_type_not_subscribed' ELSE NULL END)
  ON CONFLICT DO NOTHING;
  IF FOUND THEN RETURN p_outcome; END IF;

  SELECT * INTO v_existing
    FROM fincilia.billing_webhook_inbox
    WHERE provider_code = 'stripe'
      AND (provider_event_digest = p_event_digest
        OR provider_event_id = p_event_id)
    FOR UPDATE;
  IF NOT FOUND
     OR v_existing.provider_event_digest <> p_event_digest
     OR v_existing.provider_event_id <> p_event_id
     OR v_existing.event_type <> p_event_type
     OR v_existing.provider_created_at <> p_created_at
     OR v_existing.payload_digest <> p_payload_digest
     OR v_existing.signature_state <> 'verified' THEN
    RAISE EXCEPTION 'billing-webhook-conflict' USING ERRCODE = '23505';
  END IF;
  RETURN 'duplicate';
END;
$$;

CREATE OR REPLACE FUNCTION fincilia.apply_stripe_subscription_snapshot(
  p_event_id text, p_event_type text, p_created_at timestamptz,
  p_event_digest text, p_payload_digest text, p_customer_id text,
  p_customer_digest text, p_subscription_id text,
  p_firm_id uuid, p_plan_code text, p_price_id text,
  p_provider_status text, p_trial_end timestamptz)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $$
DECLARE
  v_inbox text;
  v_plan uuid;
  v_actor uuid;
  v_bound_customer text;
  v_bound_subscription text;
  v_binding_found boolean;
  v_current fincilia.firm_subscription%ROWTYPE;
  v_status text;
  v_event_code text;
  v_sequence integer;
  v_new_subscription uuid;
  v_trial_end timestamptz;
BEGIN
  -- El lock precede al inbox y al primer binding. Dos eventos diferentes para
  -- la misma firma no pueden observar simultaneamente ausencia de autoridad.
  PERFORM pg_advisory_xact_lock(
    hashtextextended('stripe-firm:' || p_firm_id::text, 64002));

  v_inbox := fincilia.record_stripe_webhook(
    p_event_id, p_event_type, p_created_at, p_event_digest,
    p_payload_digest, 'processing');
  IF v_inbox = 'duplicate' THEN RETURN 'duplicate'; END IF;
  IF p_customer_id !~ '^cus_[A-Za-z0-9]{8,}$'
     OR p_customer_digest !~ '^[0-9a-f]{64}$'
     OR p_subscription_id !~ '^sub_[A-Za-z0-9]{8,}$'
     OR p_plan_code NOT IN ('starter', 'business', 'accountant')
     OR p_price_id !~ '^price_[A-Za-z0-9]{8,}$' THEN
    RAISE EXCEPTION 'billing-provider-reference-invalid' USING ERRCODE = '22023';
  END IF;
  v_status := CASE
    WHEN p_provider_status = 'trialing' THEN 'trialing'
    WHEN p_provider_status = 'active' THEN 'active'
    WHEN p_provider_status IN (
      'past_due', 'unpaid', 'incomplete', 'incomplete_expired', 'paused')
      THEN 'past_due'
    WHEN p_provider_status = 'canceled' THEN 'canceled'
    ELSE NULL END;
  IF v_status IS NULL OR (v_status = 'trialing' AND p_trial_end IS NULL) THEN
    RAISE EXCEPTION 'billing-provider-status-invalid' USING ERRCODE = '22023';
  END IF;
  v_trial_end := CASE WHEN v_status = 'trialing' THEN p_trial_end ELSE NULL END;

  SELECT binding.actor_subject_id, binding.external_customer_id,
      binding.external_subscription_id
    INTO v_actor, v_bound_customer, v_bound_subscription
    FROM fincilia.billing_provider_binding binding
    WHERE binding.firm_id = p_firm_id AND binding.provider_code = 'stripe'
    FOR UPDATE;
  v_binding_found := FOUND;
  IF v_binding_found AND v_bound_customer <> p_customer_id THEN
    RAISE EXCEPTION 'billing-customer-mismatch' USING ERRCODE = '22023';
  END IF;
  IF v_binding_found AND v_status = 'canceled'
     AND v_bound_subscription IS NOT NULL
     AND v_bound_subscription <> p_subscription_id THEN
    UPDATE fincilia.billing_webhook_inbox SET processing_state = 'succeeded',
      processed_at = now(), outcome_code = 'stale_subscription_ignored'
      WHERE provider_code = 'stripe'
        AND provider_event_digest = p_event_digest;
    RETURN 'stale';
  END IF;

  SELECT plan.plan_version_id INTO v_plan
    FROM fincilia.billing_plan_version plan
    JOIN fincilia.billing_provider_price price
      ON price.plan_version_id = plan.plan_version_id
      AND price.provider_code = 'stripe' AND price.state = 'active'
    WHERE plan.plan_code = p_plan_code AND plan.catalog_state = 'commercial'
      AND price.external_price_id = p_price_id;
  IF v_plan IS NULL THEN
    RAISE EXCEPTION 'billing-price-mismatch' USING ERRCODE = '22023';
  END IF;

  IF NOT v_binding_found THEN
    SELECT attempt.created_by INTO v_actor
      FROM fincilia.billing_checkout_attempt attempt
      WHERE attempt.firm_id = p_firm_id AND attempt.plan_version_id = v_plan
        AND attempt.state = 'ready' AND attempt.expires_at >= p_created_at
        AND attempt.created_at >= p_created_at - interval '24 hours'
      ORDER BY attempt.created_at DESC LIMIT 1 FOR UPDATE;
    IF v_actor IS NULL THEN
      RAISE EXCEPTION 'billing-checkout-proof-missing' USING ERRCODE = '42501';
    END IF;
    INSERT INTO fincilia.billing_provider_binding (
      firm_id, external_customer_id, external_subscription_id, actor_subject_id)
    VALUES (p_firm_id, p_customer_id, p_subscription_id, v_actor);
  ELSE
    UPDATE fincilia.billing_provider_binding SET
      external_subscription_id = p_subscription_id,
      last_provider_event_digest = p_event_digest,
      synchronized_at = now()
      WHERE firm_id = p_firm_id;
  END IF;

  INSERT INTO fincilia.billing_account (
    firm_id, configuration_state, provider_code, provider_customer_ref,
    tax_profile_state)
  VALUES (p_firm_id, 'ready', 'stripe',
    'sha256:' || p_customer_digest, 'pending')
  ON CONFLICT (firm_id) DO UPDATE SET
    configuration_state = 'ready', provider_code = 'stripe',
    provider_customer_ref = EXCLUDED.provider_customer_ref,
    tax_profile_state = CASE
      WHEN fincilia.billing_account.tax_profile_state = 'verified'
        THEN 'verified' ELSE 'pending' END,
    updated_at = now();

  SELECT * INTO v_current FROM fincilia.firm_subscription
    WHERE firm_id = p_firm_id AND ended_at IS NULL FOR UPDATE;
  IF FOUND AND v_current.plan_version_id = v_plan
     AND v_current.status = v_status
     AND v_current.trial_ends_at IS NOT DISTINCT FROM v_trial_end THEN
    UPDATE fincilia.billing_webhook_inbox SET processing_state = 'succeeded',
      processed_at = now(), outcome_code = 'snapshot_unchanged'
      WHERE provider_code = 'stripe'
        AND provider_event_digest = p_event_digest;
    RETURN 'unchanged';
  END IF;
  v_sequence := COALESCE(v_current.sequence, 0) + 1;
  IF v_current.subscription_id IS NOT NULL THEN
    UPDATE fincilia.firm_subscription SET status = 'superseded', ended_at = now()
      WHERE subscription_id = v_current.subscription_id;
  END IF;
  INSERT INTO fincilia.firm_subscription (
    firm_id, plan_version_id, status, source_code, sequence, activated_by,
    idempotency_key, started_at, trial_ends_at)
  VALUES (p_firm_id, v_plan, v_status, 'payment_provider', v_sequence, v_actor,
    (substr(md5('stripe|' || p_event_id), 1, 8) || '-' ||
     substr(md5('stripe|' || p_event_id), 9, 4) || '-' ||
     substr(md5('stripe|' || p_event_id), 13, 4) || '-' ||
     substr(md5('stripe|' || p_event_id), 17, 4) || '-' ||
     substr(md5('stripe|' || p_event_id), 21, 12)),
    now(), v_trial_end)
  RETURNING subscription_id INTO v_new_subscription;
  v_event_code := CASE v_status WHEN 'trialing' THEN 'trial_started'
    WHEN 'active' THEN 'activated' WHEN 'past_due' THEN 'past_due'
    ELSE 'canceled' END;
  INSERT INTO fincilia.subscription_event (
    firm_id, subscription_id, actor_subject_id, event_code, reason_code)
  VALUES (p_firm_id, v_new_subscription, v_actor, v_event_code,
    'stripe_verified_webhook');
  UPDATE fincilia.billing_checkout_attempt SET state = 'consumed', updated_at = now()
    WHERE firm_id = p_firm_id AND plan_version_id = v_plan AND state = 'ready';
  UPDATE fincilia.billing_provider_binding SET
    last_provider_event_digest = p_event_digest,
    synchronized_at = now() WHERE firm_id = p_firm_id;
  UPDATE fincilia.billing_webhook_inbox SET processing_state = 'succeeded',
    processed_at = now(), outcome_code = 'subscription_materialized'
    WHERE provider_code = 'stripe'
      AND provider_event_digest = p_event_digest;
  RETURN 'materialized';
END;
$$;

REVOKE ALL ON FUNCTION fincilia.record_stripe_webhook(
  text, text, timestamptz, text, text, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION fincilia.apply_stripe_subscription_snapshot(
  text, text, timestamptz, text, text, text, text, text, uuid, text, text, text, timestamptz)
  FROM PUBLIC;

ALTER FUNCTION fincilia.record_stripe_webhook(text, text, timestamptz, text, text, text)
  OWNER TO fincilia_billing_dispatch;
ALTER FUNCTION fincilia.apply_stripe_subscription_snapshot(
  text, text, timestamptz, text, text, text, text, text, uuid, text, text, text, timestamptz)
  OWNER TO fincilia_billing_dispatch;

GRANT EXECUTE ON FUNCTION fincilia.record_stripe_webhook(
  text, text, timestamptz, text, text, text),
  fincilia.apply_stripe_subscription_snapshot(
    text, text, timestamptz, text, text, text, text, text, uuid, text, text, text, timestamptz)
  TO fincilia_app;

COMMENT ON FUNCTION fincilia.record_stripe_webhook(
  text, text, timestamptz, text, text, text) IS
  'Acepta replays byte-identicos y rechaza colisiones de ID o digest.';
COMMENT ON FUNCTION fincilia.apply_stripe_subscription_snapshot(
  text, text, timestamptz, text, text, text, text, text, uuid, text, text, text, timestamptz)
  IS 'Serializa por firma y no deja que una baja antigua cancele otra suscripcion.';

RESET ROLE;
REVOKE CREATE ON SCHEMA fincilia FROM fincilia_billing_dispatch;

-- FNC-BIL-002: Stripe provider-ready. No crea productos, precios, clientes ni
-- cobros. Las referencias exactas quedan fuera de las tablas visibles por RLS.

DO $roles$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = 'fincilia_billing_dispatch'
  ) THEN
    RAISE EXCEPTION 'fincilia_billing_dispatch role is required before V0064';
  END IF;
END
$roles$;

CREATE TABLE fincilia.billing_provider_price (
  provider_price_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plan_version_id uuid NOT NULL
    REFERENCES fincilia.billing_plan_version(plan_version_id) ON DELETE RESTRICT,
  provider_code text NOT NULL DEFAULT 'stripe' CHECK (provider_code = 'stripe'),
  external_price_id text NOT NULL CHECK (
    external_price_id ~ '^price_[A-Za-z0-9]{8,}$'),
  state text NOT NULL DEFAULT 'active' CHECK (state IN ('active', 'retired')),
  configured_by text NOT NULL CHECK (
    length(configured_by) BETWEEN 3 AND 120 AND configured_by !~ '[[:space:]]'),
  configured_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_billing_provider_price UNIQUE (provider_code, external_price_id)
);

CREATE UNIQUE INDEX uq_billing_provider_price_active_plan
  ON fincilia.billing_provider_price (plan_version_id, provider_code)
  WHERE state = 'active';

CREATE TABLE fincilia.billing_provider_binding (
  firm_id uuid PRIMARY KEY REFERENCES fincilia.firm(firm_id) ON DELETE RESTRICT,
  provider_code text NOT NULL DEFAULT 'stripe' CHECK (provider_code = 'stripe'),
  external_customer_id text NOT NULL UNIQUE CHECK (
    external_customer_id ~ '^cus_[A-Za-z0-9]{8,}$'),
  external_subscription_id text UNIQUE CHECK (
    external_subscription_id IS NULL
    OR external_subscription_id ~ '^sub_[A-Za-z0-9]{8,}$'),
  actor_subject_id uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  last_provider_event_digest text CHECK (
    last_provider_event_digest IS NULL
    OR last_provider_event_digest ~ '^[0-9a-f]{64}$'),
  synchronized_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE fincilia.billing_checkout_attempt (
  checkout_attempt_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  firm_id uuid NOT NULL REFERENCES fincilia.firm(firm_id) ON DELETE RESTRICT,
  plan_version_id uuid NOT NULL
    REFERENCES fincilia.billing_plan_version(plan_version_id) ON DELETE RESTRICT,
  plan_code text NOT NULL CHECK (plan_code IN ('starter', 'business', 'accountant')),
  idempotency_key uuid NOT NULL,
  created_by uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  state text NOT NULL DEFAULT 'reserved'
    CHECK (state IN ('reserved', 'ready', 'consumed', 'expired')),
  external_session_id text UNIQUE CHECK (
    external_session_id IS NULL OR external_session_id ~ '^cs_[A-Za-z0-9_]{8,}$'),
  session_digest text CHECK (
    session_digest IS NULL OR session_digest ~ '^[0-9a-f]{64}$'),
  expires_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_billing_checkout_idempotency UNIQUE (firm_id, idempotency_key),
  CONSTRAINT ck_billing_checkout_ready CHECK (
    (state = 'reserved' AND external_session_id IS NULL
      AND session_digest IS NULL AND expires_at IS NULL)
    OR (state <> 'reserved' AND external_session_id IS NOT NULL
      AND session_digest IS NOT NULL AND expires_at IS NOT NULL))
);

ALTER TABLE fincilia.billing_webhook_inbox
  ADD COLUMN provider_event_id text,
  ADD COLUMN event_type text,
  ADD COLUMN provider_created_at timestamptz,
  ADD COLUMN processing_state text NOT NULL DEFAULT 'legacy'
    CHECK (processing_state IN ('legacy', 'processing', 'succeeded', 'ignored')),
  ADD COLUMN processed_at timestamptz,
  ADD COLUMN outcome_code text CHECK (
    outcome_code IS NULL OR outcome_code ~ '^[a-z0-9_]{3,64}$');

ALTER TABLE fincilia.billing_webhook_inbox
  ADD CONSTRAINT ck_stripe_inbox_shape CHECK (
    provider_code <> 'stripe'
    OR (provider_event_id ~ '^evt_[A-Za-z0-9]{8,}$'
      AND event_type IS NOT NULL
      AND length(event_type) BETWEEN 3 AND 120
      AND provider_created_at IS NOT NULL
      AND signature_state = 'verified'
      AND processing_state <> 'legacy'));

CREATE UNIQUE INDEX uq_billing_stripe_event_id
  ON fincilia.billing_webhook_inbox (provider_code, provider_event_id)
  WHERE provider_event_id IS NOT NULL;

REVOKE ALL ON fincilia.billing_provider_price,
  fincilia.billing_provider_binding, fincilia.billing_checkout_attempt
  FROM PUBLIC, fincilia_app;
GRANT USAGE ON SCHEMA fincilia TO fincilia_billing_dispatch;
GRANT SELECT ON fincilia.firm, fincilia.membership, fincilia.subject,
  fincilia.billing_plan_version TO fincilia_billing_dispatch;
GRANT SELECT, INSERT, UPDATE ON fincilia.billing_account,
  fincilia.firm_subscription, fincilia.subscription_event,
  fincilia.billing_webhook_inbox, fincilia.billing_provider_binding,
  fincilia.billing_checkout_attempt TO fincilia_billing_dispatch;
GRANT SELECT ON fincilia.billing_provider_price TO fincilia_billing_dispatch;

-- El rol NOLOGIN solo atraviesa RLS dentro de las funciones SECURITY DEFINER.
DROP POLICY billing_account_membership ON fincilia.billing_account;
CREATE POLICY billing_account_membership ON fincilia.billing_account
  USING (
    current_user = 'fincilia_billing_dispatch'
    OR EXISTS (
      SELECT 1 FROM fincilia.membership membership
      WHERE membership.firm_id = billing_account.firm_id
        AND membership.subject_id::text = current_setting('fincilia.subject_id', true)
        AND membership.status = 'active'))
  WITH CHECK (
    current_user = 'fincilia_billing_dispatch'
    OR (
      configuration_state = 'unconfigured'
      AND provider_code IS NULL
      AND provider_customer_ref IS NULL
      AND billing_country IS NULL
      AND tax_profile_state = 'unconfigured'
      AND EXISTS (
        SELECT 1 FROM fincilia.membership membership
        WHERE membership.firm_id = billing_account.firm_id
          AND membership.subject_id::text = current_setting('fincilia.subject_id', true)
          AND membership.status = 'active'
          AND membership.firm_role IN ('owner', 'firm_admin'))));

DROP POLICY firm_subscription_membership ON fincilia.firm_subscription;
CREATE POLICY firm_subscription_membership ON fincilia.firm_subscription
  USING (
    current_user = 'fincilia_billing_dispatch'
    OR EXISTS (
      SELECT 1 FROM fincilia.membership membership
      WHERE membership.firm_id = firm_subscription.firm_id
        AND membership.subject_id::text = current_setting('fincilia.subject_id', true)
        AND membership.status = 'active'))
  WITH CHECK (
    current_user = 'fincilia_billing_dispatch'
    OR (
      source_code = 'self_service_evaluation'
      AND status IN ('evaluation', 'superseded')
      AND trial_ends_at IS NULL
      AND EXISTS (
        SELECT 1 FROM fincilia.billing_plan_version plan
        WHERE plan.plan_version_id = firm_subscription.plan_version_id
          AND plan.catalog_state = 'evaluation'
          AND plan.currency_code IS NULL
          AND plan.unit_amount_minor IS NULL)
      AND EXISTS (
        SELECT 1 FROM fincilia.membership membership
        WHERE membership.firm_id = firm_subscription.firm_id
          AND membership.subject_id::text = current_setting('fincilia.subject_id', true)
          AND membership.status = 'active'
          AND membership.firm_role IN ('owner', 'firm_admin'))));

DROP POLICY subscription_event_membership ON fincilia.subscription_event;
CREATE POLICY subscription_event_membership ON fincilia.subscription_event
  USING (
    current_user = 'fincilia_billing_dispatch'
    OR EXISTS (
      SELECT 1 FROM fincilia.membership membership
      WHERE membership.firm_id = subscription_event.firm_id
        AND membership.subject_id::text = current_setting('fincilia.subject_id', true)
        AND membership.status = 'active'))
  WITH CHECK (
    current_user = 'fincilia_billing_dispatch'
    OR (
      event_code IN ('evaluation_started', 'evaluation_changed')
      AND reason_code = 'uat_evaluation_selection'
      AND EXISTS (
        SELECT 1 FROM fincilia.membership membership
        WHERE membership.firm_id = subscription_event.firm_id
          AND membership.subject_id::text = current_setting('fincilia.subject_id', true)
          AND membership.status = 'active'
          AND membership.firm_role IN ('owner', 'firm_admin'))));

CREATE OR REPLACE FUNCTION fincilia.guard_evaluation_subscription_update()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $$
BEGIN
  IF OLD.ended_at IS NOT NULL
     OR NEW.subscription_id <> OLD.subscription_id
     OR NEW.firm_id <> OLD.firm_id
     OR NEW.plan_version_id <> OLD.plan_version_id
     OR NEW.source_code <> OLD.source_code
     OR NEW.sequence <> OLD.sequence
     OR NEW.activated_by <> OLD.activated_by
     OR NEW.idempotency_key <> OLD.idempotency_key
     OR NEW.started_at <> OLD.started_at
     OR NEW.trial_ends_at IS DISTINCT FROM OLD.trial_ends_at
     OR NEW.created_at <> OLD.created_at
     OR NEW.status <> 'superseded'
     OR NEW.ended_at IS NULL THEN
    RAISE EXCEPTION 'billing subscription is append-oriented'
      USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION fincilia.guard_evaluation_subscription_update() FROM PUBLIC;

CREATE FUNCTION fincilia.reserve_stripe_checkout(
  p_firm_id uuid, p_subject_id uuid, p_plan_code text, p_idempotency_key uuid)
RETURNS TABLE (
  checkout_attempt_id uuid, plan_version_id uuid, external_price_id text,
  external_customer_id text, external_session_id text, checkout_state text)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $$
DECLARE
  v_attempt fincilia.billing_checkout_attempt%ROWTYPE;
  v_plan uuid;
  v_price text;
  v_customer text;
BEGIN
  IF current_setting('fincilia.subject_id', true) <> p_subject_id::text
     OR NOT EXISTS (
       SELECT 1 FROM fincilia.membership
       WHERE firm_id = p_firm_id AND subject_id = p_subject_id
         AND status = 'active' AND firm_role IN ('owner', 'firm_admin')) THEN
    RAISE EXCEPTION 'billing-forbidden' USING ERRCODE = '42501';
  END IF;
  IF p_plan_code NOT IN ('starter', 'business', 'accountant') THEN
    RAISE EXCEPTION 'billing-plan-invalid' USING ERRCODE = '22023';
  END IF;

  SELECT * INTO v_attempt FROM fincilia.billing_checkout_attempt
    WHERE firm_id = p_firm_id AND idempotency_key = p_idempotency_key
    FOR UPDATE;
  IF FOUND THEN
    IF v_attempt.plan_code <> p_plan_code THEN
      RAISE EXCEPTION 'billing-idempotency-conflict' USING ERRCODE = '23505';
    END IF;
    SELECT binding.external_customer_id INTO v_customer
      FROM fincilia.billing_provider_binding binding
      WHERE binding.firm_id = p_firm_id;
    RETURN QUERY SELECT v_attempt.checkout_attempt_id, v_attempt.plan_version_id,
      price.external_price_id, v_customer, v_attempt.external_session_id,
      v_attempt.state
      FROM fincilia.billing_provider_price price
      WHERE price.plan_version_id = v_attempt.plan_version_id
        AND price.provider_code = 'stripe' AND price.state = 'active';
    RETURN;
  END IF;

  SELECT plan.plan_version_id, price.external_price_id
    INTO v_plan, v_price
    FROM fincilia.billing_plan_version plan
    JOIN fincilia.billing_provider_price price
      ON price.plan_version_id = plan.plan_version_id
      AND price.provider_code = 'stripe' AND price.state = 'active'
    WHERE plan.plan_code = p_plan_code AND plan.catalog_state = 'commercial'
      AND plan.currency_code IS NOT NULL AND plan.unit_amount_minor IS NOT NULL
    ORDER BY plan.version DESC LIMIT 1;
  IF v_plan IS NULL THEN
    RAISE EXCEPTION 'billing-plan-unavailable' USING ERRCODE = 'P0001';
  END IF;
  INSERT INTO fincilia.billing_checkout_attempt (
    firm_id, plan_version_id, plan_code, idempotency_key, created_by)
  VALUES (p_firm_id, v_plan, p_plan_code, p_idempotency_key, p_subject_id)
  RETURNING * INTO v_attempt;
  SELECT binding.external_customer_id INTO v_customer
    FROM fincilia.billing_provider_binding binding
    WHERE binding.firm_id = p_firm_id;
  RETURN QUERY SELECT v_attempt.checkout_attempt_id, v_plan, v_price,
    v_customer, NULL::text, 'reserved'::text;
END;
$$;

CREATE FUNCTION fincilia.complete_stripe_checkout(
  p_checkout_attempt_id uuid, p_subject_id uuid, p_external_session_id text,
  p_session_digest text, p_expires_at timestamptz)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $$
DECLARE v_attempt fincilia.billing_checkout_attempt%ROWTYPE;
BEGIN
  IF current_setting('fincilia.subject_id', true) <> p_subject_id::text
     OR p_external_session_id !~ '^cs_[A-Za-z0-9_]{8,}$'
     OR p_session_digest !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION 'billing-checkout-invalid' USING ERRCODE = '22023';
  END IF;
  SELECT * INTO v_attempt FROM fincilia.billing_checkout_attempt
    WHERE checkout_attempt_id = p_checkout_attempt_id FOR UPDATE;
  IF NOT FOUND OR v_attempt.created_by <> p_subject_id THEN
    RAISE EXCEPTION 'billing-checkout-unavailable' USING ERRCODE = '42501';
  END IF;
  IF v_attempt.state = 'ready' THEN
    IF v_attempt.external_session_id <> p_external_session_id
       OR v_attempt.session_digest <> p_session_digest THEN
      RAISE EXCEPTION 'billing-checkout-conflict' USING ERRCODE = '23505';
    END IF;
    RETURN 'replayed';
  END IF;
  IF v_attempt.state <> 'reserved' THEN
    RAISE EXCEPTION 'billing-checkout-expired' USING ERRCODE = '22023';
  END IF;
  UPDATE fincilia.billing_checkout_attempt SET
    state = 'ready', external_session_id = p_external_session_id,
    session_digest = p_session_digest, expires_at = p_expires_at,
    updated_at = now()
    WHERE checkout_attempt_id = p_checkout_attempt_id;
  RETURN 'ready';
END;
$$;

CREATE FUNCTION fincilia.stripe_portal_customer(
  p_firm_id uuid, p_subject_id uuid)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $$
DECLARE v_customer text;
BEGIN
  IF current_setting('fincilia.subject_id', true) <> p_subject_id::text
     OR NOT EXISTS (
       SELECT 1 FROM fincilia.membership
       WHERE firm_id = p_firm_id AND subject_id = p_subject_id
         AND status = 'active' AND firm_role IN ('owner', 'firm_admin')) THEN
    RAISE EXCEPTION 'billing-forbidden' USING ERRCODE = '42501';
  END IF;
  SELECT external_customer_id INTO v_customer
    FROM fincilia.billing_provider_binding WHERE firm_id = p_firm_id;
  IF v_customer IS NULL THEN
    RAISE EXCEPTION 'billing-customer-unavailable' USING ERRCODE = 'P0001';
  END IF;
  RETURN v_customer;
END;
$$;

CREATE FUNCTION fincilia.record_stripe_webhook(
  p_event_id text, p_event_type text, p_created_at timestamptz,
  p_event_digest text, p_payload_digest text, p_outcome text)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $$
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
  ON CONFLICT (provider_code, provider_event_digest) DO NOTHING;
  IF NOT FOUND THEN RETURN 'duplicate'; END IF;
  RETURN p_outcome;
END;
$$;

CREATE FUNCTION fincilia.apply_stripe_subscription_snapshot(
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
  v_current fincilia.firm_subscription%ROWTYPE;
  v_status text;
  v_event_code text;
  v_sequence integer;
  v_new_subscription uuid;
  v_trial_end timestamptz;
BEGIN
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

  SELECT binding.actor_subject_id INTO v_actor
    FROM fincilia.billing_provider_binding binding
    WHERE binding.firm_id = p_firm_id AND binding.provider_code = 'stripe'
      AND binding.external_customer_id = p_customer_id FOR UPDATE;
  IF NOT FOUND THEN
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

REVOKE ALL ON FUNCTION fincilia.reserve_stripe_checkout(uuid, uuid, text, uuid)
  FROM PUBLIC;
REVOKE ALL ON FUNCTION fincilia.complete_stripe_checkout(
  uuid, uuid, text, text, timestamptz) FROM PUBLIC;
REVOKE ALL ON FUNCTION fincilia.stripe_portal_customer(uuid, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION fincilia.record_stripe_webhook(
  text, text, timestamptz, text, text, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION fincilia.apply_stripe_subscription_snapshot(
  text, text, timestamptz, text, text, text, text, text, uuid, text, text, text, timestamptz)
  FROM PUBLIC;

ALTER FUNCTION fincilia.reserve_stripe_checkout(uuid, uuid, text, uuid)
  OWNER TO fincilia_billing_dispatch;
ALTER FUNCTION fincilia.complete_stripe_checkout(uuid, uuid, text, text, timestamptz)
  OWNER TO fincilia_billing_dispatch;
ALTER FUNCTION fincilia.stripe_portal_customer(uuid, uuid)
  OWNER TO fincilia_billing_dispatch;
ALTER FUNCTION fincilia.record_stripe_webhook(text, text, timestamptz, text, text, text)
  OWNER TO fincilia_billing_dispatch;
ALTER FUNCTION fincilia.apply_stripe_subscription_snapshot(
  text, text, timestamptz, text, text, text, text, text, uuid, text, text, text, timestamptz)
  OWNER TO fincilia_billing_dispatch;

GRANT EXECUTE ON FUNCTION fincilia.reserve_stripe_checkout(uuid, uuid, text, uuid),
  fincilia.complete_stripe_checkout(uuid, uuid, text, text, timestamptz),
  fincilia.stripe_portal_customer(uuid, uuid),
  fincilia.record_stripe_webhook(text, text, timestamptz, text, text, text),
  fincilia.apply_stripe_subscription_snapshot(
    text, text, timestamptz, text, text, text, text, text, uuid, text, text, text, timestamptz)
  TO fincilia_app;

COMMENT ON TABLE fincilia.billing_provider_binding IS
  'Referencias Stripe exactas provider-only; no PAN, CVV, email ni payload.';
COMMENT ON FUNCTION fincilia.apply_stripe_subscription_snapshot(
  text, text, timestamptz, text, text, text, text, text, uuid, text, text, text, timestamptz)
  IS 'Materializa un snapshot vigente solo tras verificacion Stripe en la API.';

-- FNC-BIL-001: catalogo versionado, suscripcion por firma y medicion minima.
-- No contiene precios definitivos ni habilita cobros. Los entitlements limitan
-- capacidad futura; nunca conceden permisos ni acceso financiero.

CREATE TABLE fincilia.billing_plan_version (
  plan_version_id uuid PRIMARY KEY,
  plan_code text NOT NULL CHECK (plan_code IN ('starter', 'business', 'accountant')),
  version integer NOT NULL CHECK (version >= 1),
  display_name text NOT NULL CHECK (length(display_name) BETWEEN 2 AND 80),
  audience_code text NOT NULL CHECK (
    audience_code IN ('small_business', 'growing_team', 'accounting_practice')),
  catalog_state text NOT NULL DEFAULT 'evaluation'
    CHECK (catalog_state IN ('evaluation', 'commercial', 'retired')),
  multi_company_portfolio boolean NOT NULL,
  team_review_workflows boolean NOT NULL,
  advanced_quality_controls boolean NOT NULL,
  foundational_security boolean NOT NULL DEFAULT true
    CHECK (foundational_security),
  basic_data_export boolean NOT NULL DEFAULT true CHECK (basic_data_export),
  max_companies integer CHECK (max_companies IS NULL OR max_companies >= 1),
  max_active_members integer CHECK (
    max_active_members IS NULL OR max_active_members >= 1),
  max_monthly_documents bigint CHECK (
    max_monthly_documents IS NULL OR max_monthly_documents >= 1),
  max_storage_bytes bigint CHECK (
    max_storage_bytes IS NULL OR max_storage_bytes >= 1048576),
  currency_code text CHECK (currency_code IS NULL OR currency_code ~ '^[A-Z]{3}$'),
  unit_amount_minor bigint CHECK (unit_amount_minor IS NULL OR unit_amount_minor >= 0),
  trial_days integer CHECK (trial_days IS NULL OR trial_days BETWEEN 1 AND 180),
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_billing_plan_version UNIQUE (plan_code, version),
  CONSTRAINT ck_billing_price_pair CHECK (
    (currency_code IS NULL) = (unit_amount_minor IS NULL)),
  CONSTRAINT ck_evaluation_has_no_commercial_claim CHECK (
    catalog_state <> 'evaluation'
    OR (currency_code IS NULL AND unit_amount_minor IS NULL AND trial_days IS NULL))
);

INSERT INTO fincilia.billing_plan_version (
  plan_version_id, plan_code, version, display_name, audience_code,
  multi_company_portfolio, team_review_workflows, advanced_quality_controls)
VALUES
  ('b1000000-0000-4000-8000-000000000001', 'starter', 1, 'Inicio',
   'small_business', false, false, false),
  ('b1000000-0000-4000-8000-000000000002', 'business', 1, 'Negocio',
   'growing_team', true, true, true),
  ('b1000000-0000-4000-8000-000000000003', 'accountant', 1, 'Contador',
   'accounting_practice', true, true, true);

CREATE TABLE fincilia.billing_account (
  billing_account_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  firm_id uuid NOT NULL REFERENCES fincilia.firm(firm_id) ON DELETE RESTRICT,
  configuration_state text NOT NULL DEFAULT 'unconfigured'
    CHECK (configuration_state IN ('unconfigured', 'ready', 'suspended')),
  provider_code text CHECK (
    provider_code IS NULL OR provider_code ~ '^[a-z][a-z0-9_]{1,31}$'),
  provider_customer_ref text CHECK (
    provider_customer_ref IS NULL OR provider_customer_ref ~ '^sha256:[0-9a-f]{64}$'),
  billing_country text CHECK (
    billing_country IS NULL OR billing_country ~ '^[A-Z]{2}$'),
  tax_profile_state text NOT NULL DEFAULT 'unconfigured'
    CHECK (tax_profile_state IN ('unconfigured', 'pending', 'verified')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_billing_account_firm UNIQUE (firm_id),
  CONSTRAINT ck_billing_provider_pair CHECK (
    (provider_code IS NULL) = (provider_customer_ref IS NULL))
);

CREATE TABLE fincilia.firm_subscription (
  subscription_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  firm_id uuid NOT NULL REFERENCES fincilia.firm(firm_id) ON DELETE RESTRICT,
  plan_version_id uuid NOT NULL
    REFERENCES fincilia.billing_plan_version(plan_version_id) ON DELETE RESTRICT,
  status text NOT NULL CHECK (
    status IN ('evaluation', 'trialing', 'active', 'past_due', 'superseded', 'canceled')),
  source_code text NOT NULL CHECK (
    source_code IN ('self_service_evaluation', 'platform_admin', 'payment_provider')),
  sequence integer NOT NULL CHECK (sequence >= 1),
  activated_by uuid NOT NULL REFERENCES fincilia.subject(subject_id) ON DELETE RESTRICT,
  idempotency_key text NOT NULL CHECK (
    idempotency_key ~ '^[0-9a-f]{8}-[0-9a-f-]{27,55}$'),
  started_at timestamptz NOT NULL DEFAULT now(),
  trial_ends_at timestamptz,
  ended_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_firm_subscription_sequence UNIQUE (firm_id, sequence),
  CONSTRAINT uq_firm_subscription_idempotency UNIQUE (firm_id, idempotency_key),
  CONSTRAINT ck_subscription_window CHECK (
    ended_at IS NULL OR ended_at >= started_at),
  CONSTRAINT ck_subscription_trial CHECK (
    (status = 'trialing' AND trial_ends_at IS NOT NULL)
    OR (status <> 'trialing' AND trial_ends_at IS NULL))
);

CREATE UNIQUE INDEX uq_firm_subscription_current
  ON fincilia.firm_subscription (firm_id) WHERE ended_at IS NULL;

CREATE TABLE fincilia.subscription_event (
  subscription_event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  firm_id uuid NOT NULL REFERENCES fincilia.firm(firm_id) ON DELETE RESTRICT,
  subscription_id uuid NOT NULL
    REFERENCES fincilia.firm_subscription(subscription_id) ON DELETE RESTRICT,
  actor_subject_id uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  event_code text NOT NULL CHECK (
    event_code IN ('evaluation_started', 'evaluation_changed', 'trial_started',
                   'activated', 'past_due', 'canceled')),
  reason_code text NOT NULL CHECK (
    length(reason_code) BETWEEN 3 AND 64 AND reason_code ~ '^[a-z0-9_]+$'),
  occurred_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE fincilia.firm_usage_event (
  usage_event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  firm_id uuid NOT NULL REFERENCES fincilia.firm(firm_id) ON DELETE RESTRICT,
  company_id uuid REFERENCES fincilia.company(company_id) ON DELETE RESTRICT,
  metric_code text NOT NULL CHECK (
    metric_code IN ('documents_uploaded', 'storage_bytes')),
  quantity bigint NOT NULL CHECK (quantity >= 0),
  idempotency_key text NOT NULL CHECK (idempotency_key ~ '^[0-9a-f]{64}$'),
  dimensions jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (dimensions = '{}'::jsonb),
  observed_at timestamptz NOT NULL DEFAULT now(),
  actor_subject_id uuid REFERENCES fincilia.subject(subject_id) ON DELETE RESTRICT,
  CONSTRAINT uq_firm_usage_idempotency UNIQUE (firm_id, metric_code, idempotency_key)
);

CREATE INDEX idx_firm_usage_month
  ON fincilia.firm_usage_event (firm_id, metric_code, observed_at);

-- Inbox provider-neutral: no contiene payload, solo la huella del evento. El
-- runtime no recibe privilegios hasta que exista firma de webhook verificada.
CREATE TABLE fincilia.billing_webhook_inbox (
  inbox_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  provider_code text NOT NULL CHECK (provider_code ~ '^[a-z][a-z0-9_]{1,31}$'),
  provider_event_digest text NOT NULL CHECK (provider_event_digest ~ '^[0-9a-f]{64}$'),
  payload_digest text NOT NULL CHECK (payload_digest ~ '^[0-9a-f]{64}$'),
  signature_state text NOT NULL DEFAULT 'unverified'
    CHECK (signature_state IN ('unverified', 'verified', 'rejected')),
  received_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_billing_provider_event UNIQUE (provider_code, provider_event_digest)
);

ALTER TABLE fincilia.billing_account ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.billing_account FORCE ROW LEVEL SECURITY;
CREATE POLICY billing_account_membership ON fincilia.billing_account
  USING (EXISTS (
    SELECT 1 FROM fincilia.membership membership
    WHERE membership.firm_id = billing_account.firm_id
      AND membership.subject_id::text = current_setting('fincilia.subject_id', true)
      AND membership.status = 'active'))
  WITH CHECK (EXISTS (
    SELECT 1 FROM fincilia.membership membership
    WHERE membership.firm_id = billing_account.firm_id
      AND membership.subject_id::text = current_setting('fincilia.subject_id', true)
      AND membership.status = 'active'
      AND membership.firm_role IN ('owner', 'firm_admin')));

ALTER TABLE fincilia.firm_subscription ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.firm_subscription FORCE ROW LEVEL SECURITY;
CREATE POLICY firm_subscription_membership ON fincilia.firm_subscription
  USING (EXISTS (
    SELECT 1 FROM fincilia.membership membership
    WHERE membership.firm_id = firm_subscription.firm_id
      AND membership.subject_id::text = current_setting('fincilia.subject_id', true)
      AND membership.status = 'active'))
  WITH CHECK (EXISTS (
    SELECT 1 FROM fincilia.membership membership
    WHERE membership.firm_id = firm_subscription.firm_id
      AND membership.subject_id::text = current_setting('fincilia.subject_id', true)
      AND membership.status = 'active'
      AND membership.firm_role IN ('owner', 'firm_admin')));

ALTER TABLE fincilia.subscription_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.subscription_event FORCE ROW LEVEL SECURITY;
CREATE POLICY subscription_event_membership ON fincilia.subscription_event
  USING (EXISTS (
    SELECT 1 FROM fincilia.membership membership
    WHERE membership.firm_id = subscription_event.firm_id
      AND membership.subject_id::text = current_setting('fincilia.subject_id', true)
      AND membership.status = 'active'))
  WITH CHECK (EXISTS (
    SELECT 1 FROM fincilia.membership membership
    WHERE membership.firm_id = subscription_event.firm_id
      AND membership.subject_id::text = current_setting('fincilia.subject_id', true)
      AND membership.status = 'active'
      AND membership.firm_role IN ('owner', 'firm_admin')));

ALTER TABLE fincilia.firm_usage_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.firm_usage_event FORCE ROW LEVEL SECURITY;
CREATE POLICY firm_usage_membership ON fincilia.firm_usage_event
  USING (EXISTS (
    SELECT 1 FROM fincilia.membership membership
    WHERE membership.firm_id = firm_usage_event.firm_id
      AND membership.subject_id::text = current_setting('fincilia.subject_id', true)
      AND membership.status = 'active'))
  WITH CHECK (EXISTS (
    SELECT 1 FROM fincilia.membership membership
    WHERE membership.firm_id = firm_usage_event.firm_id
      AND membership.subject_id::text = current_setting('fincilia.subject_id', true)
      AND membership.status = 'active'));

REVOKE ALL ON fincilia.billing_plan_version, fincilia.billing_account,
  fincilia.firm_subscription, fincilia.subscription_event,
  fincilia.firm_usage_event, fincilia.billing_webhook_inbox FROM PUBLIC;
GRANT SELECT ON fincilia.billing_plan_version TO fincilia_app;
GRANT SELECT, INSERT ON fincilia.billing_account TO fincilia_app;
GRANT SELECT, INSERT, UPDATE ON fincilia.firm_subscription TO fincilia_app;
GRANT SELECT, INSERT ON fincilia.subscription_event TO fincilia_app;
GRANT SELECT, INSERT ON fincilia.firm_usage_event TO fincilia_app;
REVOKE UPDATE, DELETE ON fincilia.billing_account,
  fincilia.subscription_event, fincilia.firm_usage_event FROM fincilia_app;
REVOKE DELETE ON fincilia.firm_subscription FROM fincilia_app;

COMMENT ON TABLE fincilia.billing_webhook_inbox IS
  'Sin privilegios runtime hasta seleccionar proveedor y verificar firma.';

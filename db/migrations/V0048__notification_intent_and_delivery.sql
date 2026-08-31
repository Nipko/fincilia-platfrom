-- FNC-NTF-001: intención y entrega externa verificable.
-- El adaptador real permanece desactivado; por eso ninguna fila nace sent o
-- delivered. Las tablas separan recordatorio interno, mensaje lógico y entrega.

CREATE TABLE fincilia.notification_preference (
  preference_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL,
  subject_id uuid NOT NULL REFERENCES fincilia.subject(subject_id) ON DELETE RESTRICT,
  channel text NOT NULL CHECK (channel = 'email'),
  purpose_code text NOT NULL CHECK (purpose_code = 'operational_reminder'),
  enabled boolean NOT NULL DEFAULT false,
  locale text NOT NULL DEFAULT 'es-CO' CHECK (locale ~ '^[a-z]{2}-[A-Z]{2}$'),
  timezone text NOT NULL DEFAULT 'America/Bogota'
    CHECK (length(timezone) BETWEEN 3 AND 64 AND timezone !~ '[[:cntrl:]]'),
  quiet_from time NOT NULL DEFAULT time '20:00',
  quiet_until time NOT NULL DEFAULT time '07:00',
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_notification_preference UNIQUE
    (company_id, subject_id, channel, purpose_code),
  CONSTRAINT fk_notification_preference_company FOREIGN KEY (company_id)
    REFERENCES fincilia.company(company_id) ON DELETE RESTRICT
);

CREATE TABLE fincilia.notification_intent (
  intent_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL,
  subject_id uuid NOT NULL REFERENCES fincilia.subject(subject_id) ON DELETE RESTRICT,
  template_code text NOT NULL CHECK (template_code IN (
    'period_due_soon', 'period_due_today', 'period_in_grace', 'period_overdue')),
  business_key text NOT NULL CHECK (
    length(business_key) BETWEEN 36 AND 200 AND business_key !~ '[[:cntrl:]]'),
  render_context jsonb NOT NULL CHECK (
    jsonb_typeof(render_context) = 'object'
    AND render_context ?& ARRAY['period_label', 'due_on', 'action_url']
    AND NOT render_context ?| ARRAY[
      'amount', 'balance', 'account', 'tax_id', 'cell', 'document', 'attachment']
    AND pg_column_size(render_context) <= 4096),
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_notification_intent UNIQUE
    (company_id, subject_id, template_code, business_key),
  CONSTRAINT uq_notification_intent_identity UNIQUE (intent_id, company_id),
  CONSTRAINT uq_notification_intent_subject UNIQUE
    (intent_id, company_id, subject_id),
  CONSTRAINT fk_notification_intent_company FOREIGN KEY (company_id)
    REFERENCES fincilia.company(company_id) ON DELETE RESTRICT
);

CREATE TABLE fincilia.notification_delivery (
  delivery_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL,
  intent_id uuid NOT NULL,
  channel text NOT NULL CHECK (channel = 'email'),
  status text NOT NULL CHECK (
    status IN ('queued', 'sent', 'delivered', 'failed', 'suppressed')),
  suppression_reason text CHECK (suppression_reason IS NULL OR suppression_reason IN (
    'user_opt_out', 'adapter_unconfigured', 'destination_unavailable')),
  idempotency_key text NOT NULL CHECK (idempotency_key ~ '^[0-9a-f]{64}$'),
  attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count BETWEEN 0 AND 12),
  available_at timestamptz NOT NULL DEFAULT now(),
  provider_message_ref text CHECK (
    provider_message_ref IS NULL OR provider_message_ref ~ '^sha256:[0-9a-f]{64}$'),
  last_error_code text CHECK (
    last_error_code IS NULL OR last_error_code ~ '^[a-z][a-z0-9_]{2,63}$'),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_notification_delivery UNIQUE (intent_id, channel),
  CONSTRAINT uq_notification_delivery_idempotency UNIQUE (idempotency_key),
  CONSTRAINT fk_notification_delivery_intent FOREIGN KEY (intent_id, company_id)
    REFERENCES fincilia.notification_intent(intent_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT ck_notification_delivery_honest CHECK (
    (status = 'suppressed' AND suppression_reason IS NOT NULL)
    OR (status <> 'suppressed' AND suppression_reason IS NULL)),
  CONSTRAINT ck_notification_provider_state CHECK (
    (status IN ('sent', 'delivered') AND provider_message_ref IS NOT NULL)
    OR (status NOT IN ('sent', 'delivered') AND provider_message_ref IS NULL))
);

-- La columna subject_id se materializa para consultar la bandeja sin confiar en
-- joins que puedan omitir el destinatario. Siempre debe coincidir con intent.
ALTER TABLE fincilia.notification_delivery
  ADD COLUMN subject_id uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  ADD CONSTRAINT fk_notification_delivery_subject FOREIGN KEY
    (intent_id, company_id, subject_id)
    REFERENCES fincilia.notification_intent(intent_id, company_id, subject_id)
    ON DELETE RESTRICT;

CREATE INDEX idx_notification_delivery_status
  ON fincilia.notification_delivery (company_id, subject_id, status, available_at);

ALTER TABLE fincilia.notification_preference ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.notification_preference FORCE ROW LEVEL SECURITY;
CREATE POLICY notification_preference_isolation ON fincilia.notification_preference
  USING (company_id = nullif(current_setting('fincilia.company_id', true), '')::uuid)
  WITH CHECK (company_id = nullif(current_setting('fincilia.company_id', true), '')::uuid);

ALTER TABLE fincilia.notification_intent ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.notification_intent FORCE ROW LEVEL SECURITY;
CREATE POLICY notification_intent_isolation ON fincilia.notification_intent
  USING (company_id = nullif(current_setting('fincilia.company_id', true), '')::uuid)
  WITH CHECK (company_id = nullif(current_setting('fincilia.company_id', true), '')::uuid);

ALTER TABLE fincilia.notification_delivery ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.notification_delivery FORCE ROW LEVEL SECURITY;
CREATE POLICY notification_delivery_isolation ON fincilia.notification_delivery
  USING (company_id = nullif(current_setting('fincilia.company_id', true), '')::uuid)
  WITH CHECK (company_id = nullif(current_setting('fincilia.company_id', true), '')::uuid);

REVOKE ALL ON fincilia.notification_preference,
  fincilia.notification_intent, fincilia.notification_delivery FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE ON fincilia.notification_preference TO fincilia_app;
GRANT SELECT, INSERT ON fincilia.notification_intent,
  fincilia.notification_delivery TO fincilia_app;
REVOKE DELETE ON fincilia.notification_preference,
  fincilia.notification_intent, fincilia.notification_delivery FROM fincilia_app;
REVOKE UPDATE, DELETE ON fincilia.notification_intent,
  fincilia.notification_delivery FROM fincilia_app;

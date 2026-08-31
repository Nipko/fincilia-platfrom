-- FNC-BIL-001: un rol de aplicacion comprometido tampoco puede inventar pagos,
-- proveedor, trial o plan activo. Solo puede manejar evaluaciones sin precio.

DROP POLICY billing_account_membership ON fincilia.billing_account;
CREATE POLICY billing_account_membership ON fincilia.billing_account
  USING (EXISTS (
    SELECT 1 FROM fincilia.membership membership
    WHERE membership.firm_id = billing_account.firm_id
      AND membership.subject_id::text = current_setting('fincilia.subject_id', true)
      AND membership.status = 'active'))
  WITH CHECK (
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
        AND membership.firm_role IN ('owner', 'firm_admin')));

DROP POLICY firm_subscription_membership ON fincilia.firm_subscription;
CREATE POLICY firm_subscription_membership ON fincilia.firm_subscription
  USING (EXISTS (
    SELECT 1 FROM fincilia.membership membership
    WHERE membership.firm_id = firm_subscription.firm_id
      AND membership.subject_id::text = current_setting('fincilia.subject_id', true)
      AND membership.status = 'active'))
  WITH CHECK (
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
        AND membership.firm_role IN ('owner', 'firm_admin')));

DROP POLICY subscription_event_membership ON fincilia.subscription_event;
CREATE POLICY subscription_event_membership ON fincilia.subscription_event
  USING (EXISTS (
    SELECT 1 FROM fincilia.membership membership
    WHERE membership.firm_id = subscription_event.firm_id
      AND membership.subject_id::text = current_setting('fincilia.subject_id', true)
      AND membership.status = 'active'))
  WITH CHECK (
    event_code IN ('evaluation_started', 'evaluation_changed')
    AND reason_code = 'uat_evaluation_selection'
    AND EXISTS (
      SELECT 1 FROM fincilia.membership membership
      WHERE membership.firm_id = subscription_event.firm_id
        AND membership.subject_id::text = current_setting('fincilia.subject_id', true)
        AND membership.status = 'active'
        AND membership.firm_role IN ('owner', 'firm_admin')));

DROP POLICY firm_usage_membership ON fincilia.firm_usage_event;
CREATE POLICY firm_usage_membership ON fincilia.firm_usage_event
  USING (EXISTS (
    SELECT 1 FROM fincilia.membership membership
    WHERE membership.firm_id = firm_usage_event.firm_id
      AND membership.subject_id::text = current_setting('fincilia.subject_id', true)
      AND membership.status = 'active'))
  WITH CHECK (
    ((metric_code = 'documents_uploaded' AND quantity = 1)
      OR (metric_code = 'storage_bytes' AND quantity BETWEEN 0 AND 26214400))
    AND dimensions = '{}'::jsonb
    AND company_id::text = current_setting('fincilia.company_id', true)
    AND actor_subject_id::text = current_setting('fincilia.subject_id', true)
    AND EXISTS (
      SELECT 1 FROM fincilia.membership membership
      WHERE membership.firm_id = firm_usage_event.firm_id
        AND membership.subject_id::text = current_setting('fincilia.subject_id', true)
        AND membership.status = 'active'));

CREATE FUNCTION fincilia.guard_evaluation_subscription_update()
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
     OR OLD.status <> 'evaluation'
     OR NEW.status <> 'superseded'
     OR NEW.ended_at IS NULL THEN
    RAISE EXCEPTION 'billing subscription is append-oriented'
      USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END;
$$;

REVOKE ALL ON FUNCTION fincilia.guard_evaluation_subscription_update() FROM PUBLIC;
CREATE TRIGGER trg_guard_evaluation_subscription_update
  BEFORE UPDATE ON fincilia.firm_subscription
  FOR EACH ROW EXECUTE FUNCTION fincilia.guard_evaluation_subscription_update();

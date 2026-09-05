-- FNC-BIL-002: la UI conoce si un plan tiene precio Stripe, pero nunca ve el
-- price_id exacto. V0064 permanece inmutable despues de su primer commit.

CREATE FUNCTION fincilia.stripe_plan_ready(p_plan_version_id uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM fincilia.billing_provider_price price
    WHERE price.plan_version_id = p_plan_version_id
      AND price.provider_code = 'stripe'
      AND price.state = 'active'
  )
$$;

REVOKE ALL ON FUNCTION fincilia.stripe_plan_ready(uuid) FROM PUBLIC;
ALTER FUNCTION fincilia.stripe_plan_ready(uuid)
  OWNER TO fincilia_billing_dispatch;
GRANT EXECUTE ON FUNCTION fincilia.stripe_plan_ready(uuid) TO fincilia_app;

COMMENT ON FUNCTION fincilia.stripe_plan_ready(uuid) IS
  'Expone solo readiness booleana del plan; nunca la referencia Stripe exacta.';

-- FNC-ADM-002: diagnóstico operativo agregado del plano de control.
--
-- La autoridad de plataforma ve capacidad y salud, no contenido financiero.
-- Cada política se concede exclusivamente al rol NOLOGIN `fincilia_identity` y
-- exige una asignación de plataforma activa para el sujeto de la sesión. La
-- función devuelve un vocabulario cerrado de conteos, sin IDs, nombres, valores,
-- referencias, payloads, códigos de error ni cardinalidad por empresa.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

GRANT SELECT ON fincilia.processing_run, fincilia.source_artifact,
  fincilia.dead_letter_item, fincilia.notification_delivery,
  fincilia.firm_subscription TO fincilia_identity;

CREATE POLICY processing_run_platform_metadata_read
  ON fincilia.processing_run FOR SELECT TO fincilia_identity
  USING (fincilia.current_subject_has_platform_role(ARRAY[
    'platform_superadmin', 'platform_operator', 'platform_auditor'
  ]));

CREATE POLICY source_artifact_platform_metadata_read
  ON fincilia.source_artifact FOR SELECT TO fincilia_identity
  USING (fincilia.current_subject_has_platform_role(ARRAY[
    'platform_superadmin', 'platform_operator', 'platform_auditor'
  ]));

CREATE POLICY dead_letter_platform_metadata_read
  ON fincilia.dead_letter_item FOR SELECT TO fincilia_identity
  USING (fincilia.current_subject_has_platform_role(ARRAY[
    'platform_superadmin', 'platform_operator', 'platform_auditor'
  ]));

CREATE POLICY notification_delivery_platform_metadata_read
  ON fincilia.notification_delivery FOR SELECT TO fincilia_identity
  USING (fincilia.current_subject_has_platform_role(ARRAY[
    'platform_superadmin', 'platform_operator', 'platform_auditor'
  ]));

CREATE POLICY firm_subscription_platform_metadata_read
  ON fincilia.firm_subscription FOR SELECT TO fincilia_identity
  USING (fincilia.current_subject_has_platform_role(ARRAY[
    'platform_superadmin', 'platform_operator', 'platform_auditor'
  ]));

GRANT CREATE ON SCHEMA fincilia TO fincilia_identity;

CREATE FUNCTION fincilia.platform_operational_diagnostics()
RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $function$
BEGIN
  IF NOT fincilia.current_subject_has_platform_role(ARRAY[
       'platform_superadmin', 'platform_operator', 'platform_auditor'
     ]) THEN
    RAISE insufficient_privilege USING MESSAGE = 'platform access denied';
  END IF;

  RETURN jsonb_build_object(
    'jobs', jsonb_build_object(
      'queued', (SELECT count(*) FROM fincilia.processing_run WHERE status = 'queued'),
      'running', (SELECT count(*) FROM fincilia.processing_run WHERE status = 'running'),
      'failed', (SELECT count(*) FROM fincilia.processing_run WHERE status = 'failed'),
      'failed_last_24h', (SELECT count(*) FROM fincilia.processing_run
        WHERE status = 'failed' AND finished_at >= statement_timestamp() - interval '24 hours')
    ),
    'evidence', jsonb_build_object(
      'artifacts', (SELECT count(*) FROM fincilia.source_artifact),
      'quarantined', (SELECT count(*) FROM fincilia.source_artifact
        WHERE status = 'quarantined'),
      'stored_bytes', (SELECT coalesce(sum(byte_size), 0)::text
        FROM fincilia.source_artifact)
    ),
    'dead_letters', jsonb_build_object(
      'open', (SELECT count(*) FROM fincilia.dead_letter_item
        WHERE resolution_state = 'open'),
      'requires_human', (SELECT count(*) FROM fincilia.dead_letter_item
        WHERE resolution_state = 'requires_human')
    ),
    'notifications', jsonb_build_object(
      'queued', (SELECT count(*) FROM fincilia.notification_delivery
        WHERE status = 'queued'),
      'failed', (SELECT count(*) FROM fincilia.notification_delivery
        WHERE status = 'failed'),
      'suppressed', (SELECT count(*) FROM fincilia.notification_delivery
        WHERE status = 'suppressed')
    ),
    'subscriptions', jsonb_build_object(
      'evaluation', (SELECT count(*) FROM fincilia.firm_subscription
        WHERE status = 'evaluation' AND ended_at IS NULL),
      'trialing', (SELECT count(*) FROM fincilia.firm_subscription
        WHERE status = 'trialing' AND ended_at IS NULL),
      'active', (SELECT count(*) FROM fincilia.firm_subscription
        WHERE status = 'active' AND ended_at IS NULL),
      'past_due', (SELECT count(*) FROM fincilia.firm_subscription
        WHERE status = 'past_due' AND ended_at IS NULL)
    )
  );
END
$function$;

COMMENT ON FUNCTION fincilia.platform_operational_diagnostics() IS
  'Conteos operativos globales allowlisted; nunca expone payload ni datos por empresa.';

ALTER FUNCTION fincilia.platform_operational_diagnostics()
  OWNER TO fincilia_identity;

REVOKE CREATE ON SCHEMA fincilia FROM fincilia_identity;

SET LOCAL ROLE fincilia_identity;
REVOKE ALL PRIVILEGES ON FUNCTION
  fincilia.platform_operational_diagnostics() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
  fincilia.platform_operational_diagnostics() TO fincilia_app;
RESET ROLE;

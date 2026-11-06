-- V0070 (FNC-SMB-005): aprobacion del motor desde el plano de plataforma.
--
-- ADR-039 seccion 6. Aprobar una version del motor sigue siendo una decision
-- humana, de plataforma y auditada; lo que cambia es que ya no exige una CLI
-- con el rol migrador. Un operador o superadmin de plataforma la aprueba desde
-- la API de `/platform`, y cada empresa publica con la version vigente sin ver
-- este paso.
--
-- Lo que no cambia:
--   * ningun rol de empresa aprueba: la funcion exige un rol de plataforma
--     activo sobre una persona activa, resuelto en la base desde el sujeto de
--     la sesion, nunca desde un parametro;
--   * se aprueba exactamente lo que se mostro: la llamada trae los componentes
--     vistos y la base los compara con los guardados antes de firmar;
--   * una version aprobada sigue congelada (V0009) y solo pasa a `superseded`;
--   * `release_approval` sigue sin `company_id` y la traza va a
--     `platform_audit_event`, que es la auditoria del plano de control.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

GRANT SELECT, UPDATE ON fincilia.engine_release TO fincilia_identity;
GRANT SELECT, INSERT ON fincilia.release_approval TO fincilia_identity;

GRANT CREATE ON SCHEMA fincilia TO fincilia_identity;
SET LOCAL ROLE fincilia_identity;

CREATE FUNCTION fincilia.platform_admin_approve_engine_release(
  p_release_key text,
  p_seen_components jsonb,
  p_components_digest text,
  p_approval_ref text,
  p_rationale text
)
RETURNS TABLE(release_id text, release_key text, state text,
              actor_identity text, approved_at timestamptz)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  actor_id uuid;
  target fincilia.engine_release%ROWTYPE;
  actor_label text;
BEGIN
  IF NOT fincilia.current_subject_has_platform_role(
       ARRAY['platform_superadmin', 'platform_operator']) THEN
    RAISE insufficient_privilege USING MESSAGE = 'platform access denied';
  END IF;
  actor_id := current_setting('fincilia.subject_id', true)::uuid;

  IF p_release_key IS NULL
     OR length(p_release_key) NOT BETWEEN 3 AND 120
     OR lower(p_release_key) IN ('latest', 'main', 'head', 'stable', 'current')
     OR p_components_digest IS NULL
     OR p_components_digest !~ '^[0-9a-f]{64}$'
     OR p_approval_ref IS NULL
     OR length(btrim(p_approval_ref)) NOT BETWEEN 3 AND 200
     OR p_rationale IS NULL
     OR length(btrim(p_rationale)) NOT BETWEEN 3 AND 500
     OR p_seen_components IS NULL
     OR jsonb_typeof(p_seen_components) <> 'array' THEN
    RAISE invalid_parameter_value USING MESSAGE = 'engine release approval is invalid';
  END IF;

  -- Un solo aprobador a la vez por version: el segundo ve el estado final.
  PERFORM pg_advisory_xact_lock(hashtextextended(p_release_key, 39006));
  SELECT * INTO target FROM fincilia.engine_release r
  WHERE r.release_key = p_release_key
  FOR UPDATE;
  IF NOT FOUND THEN
    RAISE no_data_found USING MESSAGE = 'engine release not found';
  END IF;
  IF target.state <> 'draft' THEN
    RAISE check_violation USING MESSAGE = 'only a draft engine release can be approved',
      CONSTRAINT = 'ck_platform_release_draft';
  END IF;
  IF target.components IS DISTINCT FROM p_seen_components THEN
    RAISE check_violation USING MESSAGE = 'the components changed since they were shown',
      CONSTRAINT = 'ck_platform_release_seen';
  END IF;

  actor_label := 'platform:' || actor_id::text;
  INSERT INTO fincilia.release_approval (
    approval_id, release_id, action, actor_identity, approval_ref, rationale,
    components_digest
  ) VALUES (
    gen_random_uuid(), target.release_id, 'approved', actor_label,
    btrim(p_approval_ref), btrim(p_rationale), p_components_digest
  );
  UPDATE fincilia.engine_release r
     SET state = 'approved', approval_ref = btrim(p_approval_ref)
   WHERE r.release_id = target.release_id;

  INSERT INTO fincilia.platform_audit_event (
    platform_audit_event_id, actor_subject_id, action, resource_kind,
    resource_ref, outcome, detail
  ) VALUES (
    gen_random_uuid(), actor_id, 'platform.engine_release.approve',
    'engine_release', target.release_key, 'allowed',
    jsonb_build_object('components_digest', p_components_digest,
                       'approval_ref', btrim(p_approval_ref))
  );

  release_id := target.release_id::text;
  release_key := target.release_key;
  state := 'approved';
  actor_identity := actor_label;
  approved_at := clock_timestamp();
  RETURN NEXT;
END
$function$;

REVOKE ALL PRIVILEGES ON FUNCTION fincilia.platform_admin_approve_engine_release(
  text, jsonb, text, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.platform_admin_approve_engine_release(
  text, jsonb, text, text, text) TO fincilia_app, fincilia_migrator;

COMMENT ON FUNCTION fincilia.platform_admin_approve_engine_release(
  text, jsonb, text, text, text) IS
  'Aprobacion de plataforma de una version del motor (ADR-039 §6). Exige rol de '
  'plataforma operador o superadmin; ninguna empresa aprueba versiones.';

RESET ROLE;
REVOKE CREATE ON SCHEMA fincilia FROM fincilia_identity;

-- V0022: vincula trabajos durables con la capability que autorizo crearlos.
--
-- Es una migracion expand-only: `issued_context_id` queda nullable para que los
-- trabajos creados antes del despliegue terminen. El productor nuevo siempre usa
-- la firma de cuatro argumentos y la fase contract posterior podra imponer NOT
-- NULL cuando la telemetria demuestre que no quedan productores antiguos.

ALTER TABLE fincilia.processing_run
  ADD COLUMN issued_context_id uuid;

ALTER TABLE fincilia.processing_run
  ADD CONSTRAINT fk_processing_run_issued_context
  FOREIGN KEY (company_id, issued_context_id)
  REFERENCES fincilia.issued_authorization_context(company_id, context_id);

CREATE INDEX idx_processing_run_issued_context
  ON fincilia.processing_run(company_id, issued_context_id)
  WHERE issued_context_id IS NOT NULL;

COMMENT ON COLUMN fincilia.processing_run.issued_context_id IS
  'Capability persistente que autorizo el trabajo; NULL solo para filas legacy de la fase expand.';

-- El rol sin login que posee el protocolo necesita leer solo la ruta autoritativa
-- que revalida. No recibe escritura de identidad, no tiene DDL fuera de la breve
-- cesion de CREATE usada para sustituir sus propias funciones, y el worker sigue
-- sin acceso a estas tablas.
GRANT SELECT ON fincilia.issued_authorization_context,
                fincilia.issued_authorization_revocation,
                fincilia.subject, fincilia.engagement, fincilia.membership,
                fincilia.company_grant
  TO fincilia_dispatch;

GRANT CREATE ON SCHEMA fincilia TO fincilia_dispatch;
SET LOCAL ROLE fincilia_dispatch;

-- Helper invoker-only. Cuando lo llaman las funciones definer corre con los
-- privilegios acotados de `fincilia_dispatch`; no se concede a runtime ni PUBLIC.
CREATE FUNCTION fincilia.processing_context_is_valid(
  p_run_id uuid, p_at timestamptz
) RETURNS boolean
LANGUAGE sql STABLE
SET search_path = pg_catalog, fincilia
AS $valid_context$
  SELECT coalesce((
    SELECT CASE
      -- Compatibilidad temporal para trabajos que ya existian al aplicar V0022.
      WHEN run.issued_context_id IS NULL THEN true
      ELSE EXISTS (
        SELECT 1
          FROM fincilia.issued_authorization_context issued
          JOIN fincilia.subject subject_row
            ON subject_row.subject_id = issued.subject_id
          JOIN fincilia.engagement engagement
            ON engagement.engagement_id = issued.engagement_id
           AND engagement.company_id = issued.company_id
           AND engagement.firm_id = issued.firm_id
          JOIN fincilia.membership membership
            ON membership.subject_id = issued.subject_id
           AND membership.firm_id = issued.firm_id
         WHERE issued.context_id = run.issued_context_id
           AND issued.company_id = run.company_id
           AND issued.authorization_version = run.authorization_version
           AND issued.purpose_code = 'processing_job'
           AND issued.resource_kind = 'source_artifact'
           AND issued.expires_at > p_at
           AND subject_row.status = 'active'
           AND engagement.status = 'active'
           AND (engagement.valid_to IS NULL
                OR engagement.valid_to >= p_at::date)
           AND membership.status = 'active'
           AND EXISTS (
             SELECT 1 FROM fincilia.company_grant grant_row
              WHERE grant_row.company_id = issued.company_id
                AND grant_row.subject_id = issued.subject_id
                AND grant_row.revoked_at IS NULL
           )
           AND NOT EXISTS (
             SELECT 1 FROM fincilia.issued_authorization_revocation revoked
              WHERE revoked.company_id = issued.company_id
                AND revoked.context_id = issued.context_id
           )
      )
    END
      FROM fincilia.processing_run run
     WHERE run.run_id = p_run_id
  ), false)
$valid_context$;

ALTER FUNCTION fincilia.processing_context_is_valid(uuid, timestamptz)
  OWNER TO fincilia_dispatch;
REVOKE ALL PRIVILEGES ON FUNCTION fincilia.processing_context_is_valid(uuid, timestamptz)
  FROM PUBLIC;

-- La firma nueva es la unica que usa el productor actualizado. Conservamos la
-- firma anterior durante el despliegue expand-only para binarios en vuelo y para
-- trabajos legacy; una migracion contract la retirara despues.
CREATE FUNCTION fincilia.enqueue_processing_run(
  p_company_id uuid, p_artifact_id uuid, p_kind text, p_issued_context_id uuid
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $enqueue_with_context$
DECLARE
  v_run_id  uuid;
  v_version integer;
BEGIN
  IF p_kind IS NULL OR p_kind NOT IN ('scan', 'profile', 'extract') THEN
    RAISE EXCEPTION 'unknown work kind' USING ERRCODE = '22023';
  END IF;
  IF p_issued_context_id IS NULL THEN
    RAISE EXCEPTION 'an issued authorization context is required'
      USING ERRCODE = '42501';
  END IF;
  IF p_company_id IS NULL
     OR p_company_id::text IS DISTINCT FROM
        current_setting('fincilia.company_id', true) THEN
    RAISE EXCEPTION 'the requested company does not match the authorised context'
      USING ERRCODE = '42501';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM fincilia.source_artifact artifact
     WHERE artifact.artifact_id = p_artifact_id
       AND artifact.company_id = p_company_id
  ) THEN
    RAISE EXCEPTION 'no such artifact in this context' USING ERRCODE = '42501';
  END IF;

  SELECT version.version INTO v_version
    FROM fincilia.authorization_version version
   WHERE version.company_id = p_company_id;

  IF v_version IS NULL OR NOT EXISTS (
    SELECT 1
      FROM fincilia.issued_authorization_context issued
      JOIN fincilia.subject subject_row
        ON subject_row.subject_id = issued.subject_id
      JOIN fincilia.engagement engagement
        ON engagement.engagement_id = issued.engagement_id
       AND engagement.company_id = issued.company_id
       AND engagement.firm_id = issued.firm_id
      JOIN fincilia.membership membership
        ON membership.subject_id = issued.subject_id
       AND membership.firm_id = issued.firm_id
     WHERE issued.context_id = p_issued_context_id
       AND issued.company_id = p_company_id
       AND issued.authorization_version = v_version
       AND issued.purpose_code = 'processing_job'
       AND issued.resource_kind = 'source_artifact'
       AND issued.expires_at > clock_timestamp()
       AND subject_row.status = 'active'
       AND engagement.status = 'active'
       AND (engagement.valid_to IS NULL OR engagement.valid_to >= CURRENT_DATE)
       AND membership.status = 'active'
       AND EXISTS (
         SELECT 1 FROM fincilia.company_grant grant_row
          WHERE grant_row.company_id = issued.company_id
            AND grant_row.subject_id = issued.subject_id
            AND grant_row.revoked_at IS NULL
       )
       AND NOT EXISTS (
         SELECT 1 FROM fincilia.issued_authorization_revocation revoked
          WHERE revoked.company_id = issued.company_id
            AND revoked.context_id = issued.context_id
       )
  ) THEN
    RAISE EXCEPTION 'the issued authorization context is no longer valid'
      USING ERRCODE = '42501';
  END IF;

  v_run_id := gen_random_uuid();
  INSERT INTO fincilia.processing_run (
    run_id, company_id, artifact_id, kind, authorization_version,
    issued_context_id
  ) VALUES (
    v_run_id, p_company_id, p_artifact_id, p_kind, v_version,
    p_issued_context_id
  )
  ON CONFLICT (company_id, artifact_id, kind)
    WHERE status IN ('queued', 'running')
  DO NOTHING
  RETURNING processing_run.run_id INTO v_run_id;

  IF v_run_id IS NULL THEN
    SELECT run.run_id INTO v_run_id
      FROM fincilia.processing_run run
     WHERE run.company_id = p_company_id
       AND run.artifact_id = p_artifact_id
       AND run.kind = p_kind
       AND run.status IN ('queued', 'running')
       AND run.issued_context_id = p_issued_context_id;
    IF v_run_id IS NULL THEN
      RAISE EXCEPTION 'live work belongs to another authorization context'
        USING ERRCODE = '42501';
    END IF;
    RETURN v_run_id;
  END IF;

  INSERT INTO fincilia.dispatch_pointer(run_id, company_id, kind)
  VALUES (v_run_id, p_company_id, p_kind);
  RETURN v_run_id;
END;
$enqueue_with_context$;

ALTER FUNCTION fincilia.enqueue_processing_run(uuid, uuid, text, uuid)
  OWNER TO fincilia_dispatch;
REVOKE ALL PRIVILEGES ON FUNCTION fincilia.enqueue_processing_run(uuid, uuid, text, uuid)
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
  fincilia.enqueue_processing_run(uuid, uuid, text, uuid)
  TO fincilia_app, fincilia_worker;

-- Misma interfaz publica que V0005: el worker no necesita ver identidad. La
-- diferencia es que una capability invalida se terminaliza antes de entregar el
-- trabajo.
CREATE OR REPLACE FUNCTION fincilia.claim_next_run(
  p_worker text, p_lease_seconds integer
) RETURNS TABLE (
  run_id uuid, company_id uuid, artifact_id uuid, kind text,
  attempt integer, lease_token uuid
)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $claim$
DECLARE
  v_saved   text := coalesce(current_setting('fincilia.company_id', true), '');
  v_now     timestamptz := clock_timestamp();
  v_pointer record;
  v_run     record;
  v_current integer;
  v_token   uuid;
BEGIN
  IF p_worker IS NULL OR length(p_worker) NOT BETWEEN 1 AND 80 THEN
    RAISE EXCEPTION 'a worker identity is required' USING ERRCODE = '22023';
  END IF;
  IF p_lease_seconds IS NULL OR p_lease_seconds NOT BETWEEN 10 AND 3600 THEN
    RAISE EXCEPTION 'lease seconds out of range' USING ERRCODE = '22023';
  END IF;

  FOR v_pointer IN
    SELECT pointer.run_id AS pointer_run,
           pointer.company_id AS pointer_company
      FROM fincilia.dispatch_pointer pointer
     WHERE pointer.available_at <= v_now
     ORDER BY pointer.available_at, pointer.run_id
     LIMIT 32 FOR UPDATE SKIP LOCKED
  LOOP
    PERFORM set_config('fincilia.company_id',
                       v_pointer.pointer_company::text, true);

    SELECT run.* INTO v_run
      FROM fincilia.processing_run run
     WHERE run.run_id = v_pointer.pointer_run
     FOR UPDATE;
    IF NOT FOUND THEN
      CONTINUE;
    END IF;

    IF v_run.status IN ('succeeded', 'failed') THEN
      DELETE FROM fincilia.dispatch_pointer pointer
       WHERE pointer.run_id = v_pointer.pointer_run;
      CONTINUE;
    END IF;

    IF v_run.status = 'running' AND v_run.lease_expires_at > v_now THEN
      UPDATE fincilia.dispatch_pointer pointer
         SET available_at = v_run.lease_expires_at
       WHERE pointer.run_id = v_pointer.pointer_run;
      CONTINUE;
    END IF;

    IF v_run.status = 'running' THEN
      UPDATE fincilia.run_attempt run_attempt
         SET finished_at = v_now, outcome = 'abandoned',
             failure_class = 'unknown', reason_code = 'lease_expired'
       WHERE run_attempt.run_id = v_run.run_id
         AND run_attempt.attempt_number = v_run.attempt
         AND run_attempt.outcome = 'running';

      IF v_run.attempt >= v_run.max_attempts THEN
        PERFORM fincilia.send_to_dead_letter(
          v_run.run_id, v_run.company_id, 'unknown',
          'attempts_exhausted', v_now);
        CONTINUE;
      END IF;

      UPDATE fincilia.processing_run run
         SET status = 'queued', started_at = NULL, finished_at = NULL,
             lease_token = NULL, lease_expires_at = NULL, claimed_by = NULL,
             error_code = NULL, failure_class = NULL,
             attempt = run.attempt + 1
       WHERE run.run_id = v_run.run_id;
      SELECT run.* INTO v_run FROM fincilia.processing_run run
       WHERE run.run_id = v_run.run_id;
    END IF;

    SELECT version.version INTO v_current
      FROM fincilia.authorization_version version
     WHERE version.company_id = v_run.company_id;
    IF v_run.authorization_version IS NULL
       OR v_current IS NULL
       OR v_current <> v_run.authorization_version
       OR NOT fincilia.processing_context_is_valid(v_run.run_id, v_now) THEN
      UPDATE fincilia.processing_run run
         SET status = 'failed', started_at = coalesce(run.started_at, v_now),
             finished_at = v_now, lease_token = NULL,
             lease_expires_at = NULL,
             error_code = CASE
               WHEN v_current IS DISTINCT FROM v_run.authorization_version
                 THEN 'authorization_changed'
               ELSE 'authorization_context_invalid'
             END,
             failure_class = 'requires_human'
       WHERE run.run_id = v_run.run_id;
      DELETE FROM fincilia.dispatch_pointer pointer
       WHERE pointer.run_id = v_run.run_id;
      CONTINUE;
    END IF;

    v_token := gen_random_uuid();
    UPDATE fincilia.processing_run run
       SET status = 'running', started_at = v_now, finished_at = NULL,
           lease_token = v_token,
           lease_expires_at = v_now + make_interval(secs => p_lease_seconds),
           claimed_by = p_worker, error_code = NULL, failure_class = NULL
     WHERE run.run_id = v_run.run_id;

    INSERT INTO fincilia.run_attempt(
      attempt_id, run_id, company_id, attempt_number, owner, worker,
      lease_token, policy_version, started_at
    ) VALUES (
      gen_random_uuid(), v_run.run_id, v_run.company_id, v_run.attempt,
      'document_worker', p_worker, v_token, '1', v_now
    );

    UPDATE fincilia.dispatch_pointer pointer
       SET available_at = v_now + make_interval(secs => p_lease_seconds)
     WHERE pointer.run_id = v_run.run_id;

    run_id := v_run.run_id;
    company_id := v_run.company_id;
    artifact_id := v_run.artifact_id;
    kind := v_run.kind;
    attempt := v_run.attempt;
    lease_token := v_token;
    PERFORM set_config('fincilia.company_id', v_saved, true);
    RETURN NEXT;
    RETURN;
  END LOOP;

  PERFORM set_config('fincilia.company_id', v_saved, true);
  RETURN;
END;
$claim$;

ALTER FUNCTION fincilia.claim_next_run(text, integer)
  OWNER TO fincilia_dispatch;

-- Cada lote mantiene el lock de arriendo y revalida en el mismo snapshot. Si la
-- capability ya no vive, el worker no escribe otra fila.
CREATE OR REPLACE FUNCTION fincilia.hold_processing_lease(
  p_run_id uuid, p_lease_token uuid
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $hold_lease$
BEGIN
  IF p_run_id IS NULL OR p_lease_token IS NULL THEN
    RETURN false;
  END IF;

  PERFORM 1
    FROM fincilia.processing_run run
   WHERE run.run_id = p_run_id
     AND run.company_id::text = current_setting('fincilia.company_id', true)
     AND run.status = 'running'
     AND run.lease_token = p_lease_token
     AND run.lease_expires_at > clock_timestamp()
     AND fincilia.processing_context_is_valid(
           run.run_id, clock_timestamp())
   FOR NO KEY UPDATE;

  RETURN FOUND;
END;
$hold_lease$;

ALTER FUNCTION fincilia.hold_processing_lease(uuid, uuid)
  OWNER TO fincilia_dispatch;

-- Cerrar con exito tambien es un uso de la capability. Una revocacion ocurrida
-- despues del ultimo lote no puede convertir trabajo no autorizado en exito.
CREATE OR REPLACE FUNCTION fincilia.finish_run(
  p_run_id uuid, p_lease_token uuid, p_result jsonb, p_error_code text,
  p_failure_class text
) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $finish$
DECLARE
  v_saved   text := coalesce(current_setting('fincilia.company_id', true), '');
  v_company uuid;
  v_run     record;
  v_now     timestamptz := clock_timestamp();
  v_backoff integer;
  v_outcome text;
BEGIN
  IF p_error_code IS NOT NULL
     AND p_error_code !~ '^[a-z][a-z0-9_]{2,79}$' THEN
    RAISE EXCEPTION 'reason codes are a bounded vocabulary'
      USING ERRCODE = '22023';
  END IF;
  IF (p_error_code IS NULL) <> (p_failure_class IS NULL) THEN
    RAISE EXCEPTION 'a failure needs both a reason and a class'
      USING ERRCODE = '22023';
  END IF;
  IF p_failure_class IS NOT NULL
     AND p_failure_class NOT IN (
       'retryable', 'rate_limited', 'fatal', 'requires_human', 'unknown'
     ) THEN
    RAISE EXCEPTION 'unknown failure class' USING ERRCODE = '22023';
  END IF;

  SELECT pointer.company_id INTO v_company
    FROM fincilia.dispatch_pointer pointer
   WHERE pointer.run_id = p_run_id FOR UPDATE;
  IF NOT FOUND THEN
    RETURN 'stale_lease';
  END IF;
  PERFORM set_config('fincilia.company_id', v_company::text, true);

  SELECT run.* INTO v_run FROM fincilia.processing_run run
   WHERE run.run_id = p_run_id FOR UPDATE;
  IF NOT FOUND THEN
    PERFORM set_config('fincilia.company_id', v_saved, true);
    RETURN 'not_found';
  END IF;

  IF v_run.status <> 'running'
     OR v_run.lease_token IS DISTINCT FROM p_lease_token
     OR v_run.lease_expires_at <= v_now THEN
    PERFORM set_config('fincilia.company_id', v_saved, true);
    RETURN 'stale_lease';
  END IF;

  IF NOT fincilia.processing_context_is_valid(v_run.run_id, v_now) THEN
    UPDATE fincilia.run_attempt run_attempt
       SET finished_at = v_now, outcome = 'failed',
           failure_class = 'requires_human',
           reason_code = 'authorization_context_invalid'
     WHERE run_attempt.run_id = p_run_id
       AND run_attempt.lease_token = p_lease_token;
    UPDATE fincilia.processing_run run
       SET status = 'failed', finished_at = v_now,
           lease_token = NULL, lease_expires_at = NULL,
           error_code = 'authorization_context_invalid',
           failure_class = 'requires_human'
     WHERE run.run_id = p_run_id;
    DELETE FROM fincilia.dispatch_pointer pointer
     WHERE pointer.run_id = p_run_id;
    PERFORM set_config('fincilia.company_id', v_saved, true);
    RETURN 'authorization_context_invalid';
  END IF;

  UPDATE fincilia.run_attempt run_attempt
     SET finished_at = v_now,
         outcome = CASE WHEN p_error_code IS NULL
                        THEN 'succeeded' ELSE 'failed' END,
         failure_class = p_failure_class,
         reason_code = p_error_code
   WHERE run_attempt.run_id = p_run_id
     AND run_attempt.lease_token = p_lease_token;

  IF p_error_code IS NULL THEN
    UPDATE fincilia.processing_run run
       SET status = 'succeeded', finished_at = v_now, lease_token = NULL,
           lease_expires_at = NULL, error_code = NULL, failure_class = NULL,
           result = coalesce(p_result, run.result)
     WHERE run.run_id = p_run_id;
    DELETE FROM fincilia.dispatch_pointer pointer
     WHERE pointer.run_id = p_run_id;
    v_outcome := 'succeeded';
  ELSIF p_failure_class IN ('fatal', 'requires_human') THEN
    UPDATE fincilia.processing_run run
       SET status = 'failed', finished_at = v_now, lease_token = NULL,
           lease_expires_at = NULL, error_code = p_error_code,
           failure_class = p_failure_class
     WHERE run.run_id = p_run_id;
    DELETE FROM fincilia.dispatch_pointer pointer
     WHERE pointer.run_id = p_run_id;
    v_outcome := 'failed';
  ELSIF v_run.attempt >= v_run.max_attempts THEN
    PERFORM fincilia.send_to_dead_letter(
      p_run_id, v_company, p_failure_class, 'attempts_exhausted', v_now);
    v_outcome := 'dead_letter';
  ELSE
    v_backoff := least(300, 5 * (2 ^ v_run.attempt)::integer);
    UPDATE fincilia.processing_run run
       SET status = 'queued', started_at = NULL, finished_at = NULL,
           lease_token = NULL, lease_expires_at = NULL, claimed_by = NULL,
           error_code = NULL, failure_class = NULL,
           attempt = run.attempt + 1
     WHERE run.run_id = p_run_id;
    UPDATE fincilia.dispatch_pointer pointer
       SET available_at = v_now + make_interval(secs => v_backoff)
     WHERE pointer.run_id = p_run_id;
    v_outcome := 'requeued';
  END IF;

  PERFORM set_config('fincilia.company_id', v_saved, true);
  RETURN v_outcome;
END;
$finish$;

ALTER FUNCTION fincilia.finish_run(uuid, uuid, jsonb, text, text)
  OWNER TO fincilia_dispatch;

-- CREATE OR REPLACE conserva ACL, pero se repite el cierre explicito porque una
-- funcion nueva es ejecutable por PUBLIC en PostgreSQL si nadie lo retira.
REVOKE ALL PRIVILEGES ON FUNCTION
  fincilia.claim_next_run(text, integer) FROM PUBLIC;
REVOKE ALL PRIVILEGES ON FUNCTION
  fincilia.hold_processing_lease(uuid, uuid) FROM PUBLIC;
REVOKE ALL PRIVILEGES ON FUNCTION
  fincilia.finish_run(uuid, uuid, jsonb, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.claim_next_run(text, integer)
  TO fincilia_worker;
GRANT EXECUTE ON FUNCTION fincilia.hold_processing_lease(uuid, uuid)
  TO fincilia_worker;
GRANT EXECUTE ON FUNCTION
  fincilia.finish_run(uuid, uuid, jsonb, text, text)
  TO fincilia_worker;

RESET ROLE;
REVOKE CREATE ON SCHEMA fincilia FROM fincilia_dispatch;

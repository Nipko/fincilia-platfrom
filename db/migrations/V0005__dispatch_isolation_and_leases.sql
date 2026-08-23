-- V0005: aislamiento del despachador, arriendos durables y privilegios minimos.
--
-- Tres defectos reales, encontrados en revision independiente. Ninguno se podia
-- arreglar editando V0001..V0004: ya estan aplicadas y su checksum es inmutable
-- a proposito.
--
-- 1. **El puntero de despacho no estaba ligado a la empresa de su trabajo.**
--    `dispatch_pointer.run_id` referenciaba `processing_run`, pero `company_id`
--    era una columna suelta: nada impedia un puntero con el trabajo de la
--    empresa A y la empresa B. Ahora la clave ajena es compuesta y el motor lo
--    rechaza.
--
-- 2. **Un trabajo podia quedarse en `running` para siempre.** El worker marcaba
--    `running` y, si moria, solo se liberaba el puntero: el siguiente worker no
--    lo encontraba en `queued`, borraba el puntero, y el trabajo quedaba fuera de
--    toda cola y de toda lista. Ahora hay arriendo con testigo, recuperacion
--    coherente de las dos filas en una transaccion, reintentos contados y carta
--    muerta al agotarlos.
--
-- 3. **`ALTER DEFAULT PRIVILEGES` de V0001 concedia SELECT, INSERT y UPDATE al
--    rol de la API sobre toda tabla creada despues.** Incluia
--    `fincilia.local_credential`, que no tiene RLS: el rol de la API podia
--    reescribir el hash de contrasena de cualquier sujeto y entrar como el. El
--    `GRANT SELECT` de V0002 no restringia nada; repetia un bit ya puesto. Es la
--    clase de privilegio que nadie revisa porque nadie lo escribio.
--
-- Sobre `SECURITY DEFINER`: `spikes/FNC-P2.1` comprueba contra el motor que una
-- funcion `SECURITY DEFINER` **no** se salta `FORCE ROW LEVEL SECURITY`, ni
-- siquiera cuando su dueno es el dueno de la tabla. Lo que si hace es saltarse
-- los privilegios de tabla, y por eso el dueno de estas funciones **no** es el
-- migrador -- que tiene CREATE sobre la base -- sino `fincilia_dispatch`, un rol
-- sin login, sin DDL, y con exactamente los privilegios de cola que las tres
-- funciones necesitan. Ejecutar una funcion concede su efecto, nunca mas.

-- Una migracion que espera indefinidamente por un bloqueo es una migracion que
-- bloquea a todo lo que venga detras.
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

-- --------------------------------------------------------------------------- --
-- 0. Los roles tienen que existir, y se dice claro si faltan
-- --------------------------------------------------------------------------- --

-- El migrador es NOCREATEROLE a proposito: crear roles es aprovisionamiento de
-- cluster, no cambio de esquema. Los crea `infra/local/db/init/001_bootstrap.sql`.
-- Si faltan, esto se detiene diciendo que hacer. Un GRANT condicional que se
-- salta en silencio produce un sistema a medio privilegiar que se descubre mucho
-- despues, dentro de un trabajo, como un error de permisos.
DO $roles$
DECLARE
  v_missing text[] := ARRAY[]::text[];
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fincilia_worker') THEN
    v_missing := v_missing || 'fincilia_worker';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fincilia_dispatch') THEN
    v_missing := v_missing || 'fincilia_dispatch';
  END IF;
  IF array_length(v_missing, 1) IS NOT NULL THEN
    RAISE EXCEPTION USING
      ERRCODE = '28000',
      MESSAGE = format('V0005 requires roles %s', array_to_string(v_missing, ', ')),
      HINT = 'they are created by infra/local/db/init/001_bootstrap.sql, which only '
             'runs on an empty volume: recreate it with `docker compose -f '
             'infra/local/compose.yaml -p fincilia-local down --volumes`';
  END IF;
END
$roles$;

-- --------------------------------------------------------------------------- --
-- 1. Cortar el grant automatico ANTES de crear nada
-- --------------------------------------------------------------------------- --

-- El orden es la mitad del arreglo. `ALTER DEFAULT PRIVILEGES` se aplica a los
-- objetos creados **despues** de registrarse, asi que retirarlo aqui arriba es lo
-- que impide que `run_attempt` y `dead_letter_item` nazcan con SELECT, INSERT y
-- UPDATE para la API sin que nadie lo haya escrito. La sentencia tiene que
-- coincidir exactamente con la que lo registro, o la fila de `pg_default_acl` no
-- se elimina y el problema sigue ahi, callado.
ALTER DEFAULT PRIVILEGES FOR ROLE fincilia_migrator IN SCHEMA fincilia
  REVOKE SELECT, INSERT, UPDATE ON TABLES FROM fincilia_app;

GRANT USAGE ON SCHEMA fincilia TO fincilia_worker, fincilia_dispatch;

-- --------------------------------------------------------------------------- --
-- 2. Lo que el grant automatico ya habia concedido, retirado a mano
-- --------------------------------------------------------------------------- --

-- No es retroactivo en ninguna direccion, asi que retirarlo arriba no toca lo ya
-- concedido. Este es el defecto 3, y el mas serio de los tres.
REVOKE INSERT, UPDATE ON fincilia.local_credential FROM fincilia_app;

-- La API nunca ha actualizado un trabajo: `bump_authorization_version` era su
-- unico UPDATE en todo el codigo, y no lo llama nadie.
REVOKE UPDATE ON fincilia.processing_run FROM fincilia_app;

-- `identity_binding` y `firm` no los lee nadie desde la API: la autorizacion sale
-- de engagement, membership y company_grant. Un privilegio que no se ejerce es
-- superficie que alguien tendra que justificar mas adelante.
REVOKE ALL PRIVILEGES ON fincilia.identity_binding, fincilia.firm FROM fincilia_app;

-- Y la cola deja de ser escribible directamente por la API. Encolar pasa a ser
-- una funcion con parametros validados; no un INSERT libre sobre una tabla
-- global sin RLS.
REVOKE ALL PRIVILEGES ON fincilia.dispatch_pointer FROM fincilia_app;
REVOKE ALL PRIVILEGES ON fincilia.processing_run FROM fincilia_app;
GRANT SELECT ON fincilia.processing_run TO fincilia_app;

-- Nota deliberada: **no** se retiran INSERT ni UPDATE sobre `engagement`,
-- `company_grant` ni `authorization_version`. El DFD declara F13
-- (`engagement_revocation`) como una accion del producto, con efecto autoritativo
-- sobre el estado de autorizacion. Retirarlos convertiria revocar un acceso en
-- una intervencion manual de operador, que es debilitar el control C-REVOKE en
-- vez de reforzarlo.

-- --------------------------------------------------------------------------- --
-- 3. Integridad del puntero de despacho
-- --------------------------------------------------------------------------- --

ALTER TABLE fincilia.processing_run
  ADD CONSTRAINT uq_run_company UNIQUE (run_id, company_id);

-- La unicidad anterior era `(artifact_id, kind, attempt)`, y ataba la
-- idempotencia al contador de intentos: en cuanto un reintento subia `attempt`,
-- el hueco 1 quedaba libre y una segunda subida creaba un **segundo trabajo
-- vivo** para el mismo artefacto. Lo que hay que impedir es que existan dos
-- trabajos vivos, no que un trabajo se reintente.
CREATE UNIQUE INDEX uq_run_live
  ON fincilia.processing_run (company_id, artifact_id, kind)
  WHERE status IN ('queued', 'running');

ALTER TABLE fincilia.processing_run DROP CONSTRAINT uq_run_attempt;

-- Cuando el trabajo vuelve a estar disponible. Marca de tiempo, no dato de
-- negocio: sigue dentro de lo que declara la excepcion de RLS del puntero.
ALTER TABLE fincilia.dispatch_pointer
  ADD COLUMN available_at timestamptz NOT NULL DEFAULT now();

CREATE INDEX idx_dispatch_available ON fincilia.dispatch_pointer (available_at, run_id);

-- Las columnas `claimed_at` y `claimed_by` de V0004 dejan de usarse: el arriendo
-- vive en `processing_run`, donde RLS lo protege. No se pueden eliminar porque
-- V0004 esta aplicada; se vacian y el esquema prohibe volver a escribirlas.
UPDATE fincilia.dispatch_pointer SET claimed_at = NULL, claimed_by = NULL
 WHERE claimed_at IS NOT NULL OR claimed_by IS NOT NULL;

ALTER TABLE fincilia.dispatch_pointer
  ADD CONSTRAINT ck_dispatch_claim_unused
  CHECK (claimed_at IS NULL AND claimed_by IS NULL);

ALTER TABLE fincilia.dispatch_pointer
  DROP CONSTRAINT dispatch_pointer_run_id_fkey;

-- El corazon del defecto 1: la pareja tiene que coincidir, y lo comprueba el
-- motor, no el codigo que inserta.
ALTER TABLE fincilia.dispatch_pointer
  ADD CONSTRAINT fk_dispatch_run_company
  FOREIGN KEY (run_id, company_id) REFERENCES fincilia.processing_run (run_id, company_id);

-- --------------------------------------------------------------------------- --
-- 4. Arriendo y reintentos
-- --------------------------------------------------------------------------- --

ALTER TABLE fincilia.processing_run
  ADD COLUMN lease_token           uuid,
  ADD COLUMN lease_expires_at      timestamptz,
  ADD COLUMN claimed_by            text CHECK (claimed_by IS NULL
                                               OR length(claimed_by) BETWEEN 1 AND 80),
  ADD COLUMN failure_class         text,
  ADD COLUMN max_attempts          integer NOT NULL DEFAULT 3
                                     CHECK (max_attempts BETWEEN 1 AND 10),
  -- La autorizacion vigente cuando se encolo. El contrato de autorizacion declara
  -- `authorization_version_on_work: true`: sin esto, revocar un acceso no detiene
  -- el trabajo que ya estaba en cola.
  ADD COLUMN authorization_version integer;

-- Reparacion de una vez: lo que quedo colgado en `running` vuelve a la cola. Es
-- exactamente el estado que este cambio impide crear, y conservar el sintoma tras
-- arreglar la causa no ayuda a nadie.
UPDATE fincilia.processing_run
   SET status = 'queued', started_at = NULL, finished_at = NULL
 WHERE status = 'running';

-- No se anade un estado `dead_letter`: `failed` con `error_code` y una fila en
-- `dead_letter_item` dice lo mismo, satisface las restricciones de V0003 tal como
-- estan escritas, y se mantiene mas cerca del enum `job_state` ya declarado en
-- `docs/domain/canonical-model.json`. La visibilidad de la carta muerta viene de
-- su propia tabla, que es donde el contrato la pone.

-- Un trabajo esta en curso exactamente cuando tiene arriendo vivo. Sin este
-- acoplamiento, «running» podria significar dos cosas distintas.
ALTER TABLE fincilia.processing_run
  ADD CONSTRAINT ck_run_lease CHECK (
    (status = 'running' AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL
     AND claimed_by IS NOT NULL)
    OR (status <> 'running' AND lease_token IS NULL AND lease_expires_at IS NULL));

ALTER TABLE fincilia.processing_run
  ADD CONSTRAINT ck_run_failure_class CHECK (
    failure_class IS NULL
    OR failure_class IN ('retryable', 'rate_limited', 'fatal', 'requires_human',
                         'unknown'));

-- --------------------------------------------------------------------------- --
-- 5. Historial de intentos, append-only
-- --------------------------------------------------------------------------- --

-- Materializa el `delivery_attempt_contract` de `docs/architecture/events-retries.json`.
-- Correspondencia de nombres, explicita para que nadie tenga que adivinarla:
--   work_id -> run_id, company_scope -> company_id, fencing_token -> lease_token.
-- `company_id` se llama asi y no `company_scope` por una razon mecanica: el
-- validador de migraciones solo exige RLS a las tablas cuyo cuerpo contiene esa
-- cadena, y renombrarla dejaria la tabla fuera de la comprobacion.
--
-- `raw_error_or_payload_forbidden`: aqui caben un codigo acotado y una clase de
-- fallo, nunca el error del motor ni un fragmento del fichero.
CREATE TABLE fincilia.run_attempt (
  attempt_id     uuid PRIMARY KEY,
  run_id         uuid NOT NULL,
  company_id     uuid NOT NULL,
  attempt_number integer NOT NULL CHECK (attempt_number BETWEEN 1 AND 10),
  owner          text NOT NULL CHECK (length(owner) BETWEEN 1 AND 80),
  worker         text NOT NULL CHECK (length(worker) BETWEEN 1 AND 80),
  lease_token    uuid NOT NULL,
  policy_version text NOT NULL CHECK (length(policy_version) BETWEEN 1 AND 20),
  started_at     timestamptz NOT NULL DEFAULT now(),
  finished_at    timestamptz,
  outcome        text NOT NULL DEFAULT 'running'
                   CHECK (outcome IN ('running', 'succeeded', 'failed', 'abandoned')),
  failure_class  text CHECK (failure_class IS NULL
                             OR failure_class IN ('retryable', 'rate_limited', 'fatal',
                                                  'requires_human', 'unknown')),
  reason_code    text CHECK (reason_code IS NULL
                             OR reason_code ~ '^[a-z][a-z0-9_]{2,79}$'),
  cost_bucket    text NOT NULL DEFAULT 'local_synthetic',
  trace_id       text CHECK (trace_id IS NULL OR length(trace_id) BETWEEN 1 AND 64),
  CONSTRAINT uq_run_attempt_number UNIQUE (run_id, attempt_number),
  CONSTRAINT fk_run_attempt_run
    FOREIGN KEY (run_id, company_id)
    REFERENCES fincilia.processing_run (run_id, company_id),
  CONSTRAINT ck_run_attempt_timeline CHECK (
    (outcome = 'running' AND finished_at IS NULL)
    OR (outcome <> 'running' AND finished_at IS NOT NULL AND finished_at >= started_at))
);

CREATE INDEX idx_run_attempt_run ON fincilia.run_attempt (run_id, attempt_number);

ALTER TABLE fincilia.run_attempt ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.run_attempt FORCE ROW LEVEL SECURITY;
CREATE POLICY run_attempt_isolation ON fincilia.run_attempt
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

REVOKE ALL PRIVILEGES ON fincilia.run_attempt FROM fincilia_app;

-- --------------------------------------------------------------------------- --
-- 6. Carta muerta
-- --------------------------------------------------------------------------- --

-- Materializa el `dead_letter_contract` declarado. Dos campos no se pueden
-- satisfacer con hechos que existan hoy, y se declaran como lo que son en vez de
-- inventarlos:
--
-- - `work_class`: ninguna de las cinco clases declaradas describe una cola en
--   PostgreSQL. Se guarda la mas cercana (`stateless_job`) y la divergencia queda
--   anotada en el handoff. No se anade una sexta clase por la puerta de atras.
-- - `work_schema_version`: no hay outbox ni registro de esquemas (el contrato lo
--   exige y lo tiene diferido). La columna existe y guarda la version canonica
--   del trabajo, como marcador hasta que el registro exista.
--
-- `raw_payload_forbidden` se sostiene en el esquema: solo cabe una **referencia**
-- al contenido, nunca el contenido. Y esta tabla no decide nada financiero.
CREATE TABLE fincilia.dead_letter_item (
  dead_letter_id       uuid PRIMARY KEY,
  company_id           uuid NOT NULL REFERENCES fincilia.company(company_id),
  work_class           text NOT NULL CHECK (work_class = 'stateless_job'),
  work_id              uuid NOT NULL,
  work_schema_version  text NOT NULL CHECK (length(work_schema_version) BETWEEN 1 AND 20),
  payload_reference    text NOT NULL CHECK (payload_reference ~ '^[0-9a-f]{64}$'),
  failure_class        text NOT NULL
                         CHECK (failure_class IN ('retryable', 'rate_limited', 'fatal',
                                                  'requires_human', 'unknown')),
  reason_code          text NOT NULL CHECK (reason_code ~ '^[a-z][a-z0-9_]{2,79}$'),
  attempt_count        integer NOT NULL CHECK (attempt_count >= 1),
  first_failed_at      timestamptz NOT NULL,
  last_failed_at       timestamptz NOT NULL,
  retry_policy_version text NOT NULL CHECK (length(retry_policy_version) BETWEEN 1 AND 20),
  owner                text NOT NULL CHECK (length(owner) BETWEEN 1 AND 60),
  resolution_state     text NOT NULL DEFAULT 'open'
                         CHECK (resolution_state IN ('open', 'triaged', 'replay_approved',
                                                     'replayed', 'discarded_with_reason',
                                                     'requires_human')),
  audit_event_id       uuid,
  created_at           timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_dead_letter_work UNIQUE (work_class, work_id),
  CONSTRAINT ck_dead_letter_window CHECK (last_failed_at >= first_failed_at)
);

CREATE INDEX idx_dead_letter_open
  ON fincilia.dead_letter_item (company_id, created_at DESC)
  WHERE resolution_state = 'open';

ALTER TABLE fincilia.dead_letter_item ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.dead_letter_item FORCE ROW LEVEL SECURITY;
CREATE POLICY dead_letter_isolation ON fincilia.dead_letter_item
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

REVOKE ALL PRIVILEGES ON fincilia.dead_letter_item FROM fincilia_app;

-- --------------------------------------------------------------------------- --
-- 7. Tres funciones estrechas: la unica via de escritura sobre la cola
-- --------------------------------------------------------------------------- --
--
-- Cada una fija `search_path` explicitamente. Sin eso, un objeto colocado en un
-- esquema anterior de la ruta de busqueda del llamante se ejecutaria con los
-- privilegios del dueno de la funcion, que es la escalada clasica de
-- `SECURITY DEFINER`.
--
-- Ninguna se salta RLS -- el spike lo comprueba contra el motor -- asi que todas
-- fijan el contexto de empresa y lo **restauran** antes de salir. La restauracion
-- no es higiene: `Database.session()` fija el contexto una vez al abrir la
-- transaccion y no lo vuelve a mirar, de modo que un contexto filtrado
-- reetiquetaria en silencio todo lo que viniera despues en esa transaccion.
--
-- El orden de bloqueo es siempre el mismo, puntero y despues trabajo. Dos ordenes
-- distintos entre reclamar y terminar producirian un interbloqueo justo cuando un
-- arriendo vence mientras su dueno esta terminando, que es el caso que este
-- diseno existe para manejar.

CREATE FUNCTION fincilia.enqueue_processing_run(
  p_company_id uuid, p_artifact_id uuid, p_kind text) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $enqueue$
DECLARE
  v_run_id  uuid;
  v_version integer;
BEGIN
  IF p_kind IS NULL OR p_kind NOT IN ('profile', 'extract') THEN
    RAISE EXCEPTION 'unknown work kind' USING ERRCODE = '22023';
  END IF;
  -- El alcance no lo elige quien llama: se compara contra el contexto que el
  -- servidor ya autorizo. Encolar para otra empresa seria lo primero que habria
  -- que intentar contra esta funcion, y es lo primero que se comprueba.
  IF p_company_id IS NULL
     OR p_company_id::text IS DISTINCT FROM current_setting('fincilia.company_id', true) THEN
    RAISE EXCEPTION 'the requested company does not match the authorised context'
      USING ERRCODE = '42501';
  END IF;
  -- Y el artefacto tiene que ser visible **bajo la politica**, no solo existir.
  IF NOT EXISTS (SELECT 1 FROM fincilia.source_artifact a
                  WHERE a.artifact_id = p_artifact_id
                    AND a.company_id = p_company_id) THEN
    RAISE EXCEPTION 'no such artifact in this context' USING ERRCODE = '42501';
  END IF;

  SELECT v.version INTO v_version
    FROM fincilia.authorization_version v
   WHERE v.company_id = p_company_id;
  IF v_version IS NULL THEN
    -- Sin version de autorizacion no hay forma de invalidar el trabajo si el
    -- acceso se revoca. Falta un invariante, no un dato opcional.
    RAISE EXCEPTION 'company has no authorization version' USING ERRCODE = '42501';
  END IF;

  v_run_id := gen_random_uuid();
  INSERT INTO fincilia.processing_run (run_id, company_id, artifact_id, kind,
                                       authorization_version)
  VALUES (v_run_id, p_company_id, p_artifact_id, p_kind, v_version)
  ON CONFLICT (company_id, artifact_id, kind) WHERE status IN ('queued', 'running')
  DO NOTHING
  RETURNING processing_run.run_id INTO v_run_id;

  IF v_run_id IS NULL THEN
    -- Ya habia trabajo vivo de ese tipo para ese artefacto. Encolar dos veces es
    -- la forma mas facil de procesar dos veces la misma evidencia.
    SELECT r.run_id INTO v_run_id FROM fincilia.processing_run r
     WHERE r.company_id = p_company_id AND r.artifact_id = p_artifact_id
       AND r.kind = p_kind AND r.status IN ('queued', 'running');
    IF v_run_id IS NULL THEN
      -- El conflicto existe pero no se ve bajo la politica. Reportarlo como exito
      -- seria afirmar algo que no se puede comprobar.
      RAISE EXCEPTION 'conflicting work is not visible in this context'
        USING ERRCODE = '42501';
    END IF;
    RETURN v_run_id;
  END IF;

  -- En la MISMA transaccion que el trabajo. Si fueran dos, un fallo entre medias
  -- dejaria un trabajo que ningun worker ve.
  INSERT INTO fincilia.dispatch_pointer (run_id, company_id, kind)
  VALUES (v_run_id, p_company_id, p_kind);
  RETURN v_run_id;
END;
$enqueue$;

CREATE FUNCTION fincilia.claim_next_run(p_worker text, p_lease_seconds integer)
RETURNS TABLE (run_id uuid, company_id uuid, artifact_id uuid, kind text,
               attempt integer, lease_token uuid)
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

  -- El puntero es lo unico legible sin contexto de empresa, y solo lleva
  -- identificadores y marcas de tiempo. Es el arranque en frio de un
  -- planificador que trabaja para varias empresas.
  FOR v_pointer IN
    SELECT p.run_id AS pointer_run, p.company_id AS pointer_company
      FROM fincilia.dispatch_pointer p
     WHERE p.available_at <= v_now
     ORDER BY p.available_at, p.run_id
     LIMIT 32
       FOR UPDATE SKIP LOCKED
  LOOP
    PERFORM set_config('fincilia.company_id', v_pointer.pointer_company::text, true);

    SELECT r.* INTO v_run
      FROM fincilia.processing_run r
     WHERE r.run_id = v_pointer.pointer_run
       FOR UPDATE;
    IF NOT FOUND THEN
      CONTINUE;
    END IF;

    IF v_run.status IN ('succeeded', 'failed') THEN
      -- El trabajo termino y el puntero sobrevivio a su utilidad. Limpiarlo aqui
      -- es lo que impide que un puntero huerfano ocupe la cabeza de la cola.
      DELETE FROM fincilia.dispatch_pointer d WHERE d.run_id = v_pointer.pointer_run;
      CONTINUE;
    END IF;

    IF v_run.status = 'running' AND v_run.lease_expires_at > v_now THEN
      -- Arriendo vivo: es de otro. Se aparta el puntero hasta que venza, en vez
      -- de volver a mirarlo en cada vuelta.
      UPDATE fincilia.dispatch_pointer d SET available_at = v_run.lease_expires_at
       WHERE d.run_id = v_pointer.pointer_run;
      CONTINUE;
    END IF;

    IF v_run.status = 'running' THEN
      -- Arriendo vencido: el intento anterior se cierra como abandonado antes de
      -- abrir otro. Sin esto el historial diria que sigue en curso para siempre.
      UPDATE fincilia.run_attempt a
         SET finished_at = v_now, outcome = 'abandoned',
             failure_class = 'unknown', reason_code = 'lease_expired'
       WHERE a.run_id = v_run.run_id
         AND a.attempt_number = v_run.attempt
         AND a.outcome = 'running';

      IF v_run.attempt >= v_run.max_attempts THEN
        -- Un trabajo que agota sus intentos muriendose no vuelve a la cola: se
        -- hace visible como carta muerta.
        PERFORM fincilia.send_to_dead_letter(v_run.run_id, v_run.company_id,
                                             'unknown', 'attempts_exhausted', v_now);
        CONTINUE;
      END IF;

      UPDATE fincilia.processing_run r
         SET status = 'queued', started_at = NULL, finished_at = NULL,
             lease_token = NULL, lease_expires_at = NULL, claimed_by = NULL,
             error_code = NULL, failure_class = NULL, attempt = r.attempt + 1
       WHERE r.run_id = v_run.run_id;
      SELECT r.* INTO v_run FROM fincilia.processing_run r WHERE r.run_id = v_run.run_id;
    END IF;

    -- La autorizacion se revalida en el momento de trabajar, no solo al encolar.
    -- Revocar un acceso tiene que detener lo que ya estaba en cola.
    SELECT v.version INTO v_current
      FROM fincilia.authorization_version v WHERE v.company_id = v_run.company_id;
    IF v_run.authorization_version IS NULL
       OR v_current IS NULL
       OR v_current <> v_run.authorization_version THEN
      UPDATE fincilia.processing_run r
         SET status = 'failed', started_at = coalesce(r.started_at, v_now),
             finished_at = v_now, lease_token = NULL, lease_expires_at = NULL,
             error_code = 'authorization_changed', failure_class = 'requires_human'
       WHERE r.run_id = v_run.run_id;
      DELETE FROM fincilia.dispatch_pointer d WHERE d.run_id = v_run.run_id;
      CONTINUE;
    END IF;

    v_token := gen_random_uuid();
    UPDATE fincilia.processing_run r
       SET status = 'running', started_at = v_now, finished_at = NULL,
           lease_token = v_token,
           lease_expires_at = v_now + make_interval(secs => p_lease_seconds),
           claimed_by = p_worker, error_code = NULL, failure_class = NULL
     WHERE r.run_id = v_run.run_id;

    INSERT INTO fincilia.run_attempt (attempt_id, run_id, company_id, attempt_number,
                                      owner, worker, lease_token, policy_version,
                                      started_at)
    VALUES (gen_random_uuid(), v_run.run_id, v_run.company_id, v_run.attempt,
            'document_worker', p_worker, v_token, '1', v_now);

    UPDATE fincilia.dispatch_pointer d
       SET available_at = v_now + make_interval(secs => p_lease_seconds)
     WHERE d.run_id = v_run.run_id;

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

-- Carta muerta. Se llama siempre con el contexto de la empresa ya fijado por
-- quien llama, que en las dos rutas es otra de estas funciones.
CREATE FUNCTION fincilia.send_to_dead_letter(
  p_run_id uuid, p_company_id uuid, p_failure_class text, p_reason_code text,
  p_now timestamptz) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $dlq$
DECLARE
  v_run    record;
  v_digest text;
  v_first  timestamptz;
BEGIN
  SELECT r.* INTO v_run FROM fincilia.processing_run r WHERE r.run_id = p_run_id;
  IF NOT FOUND THEN
    RETURN;
  END IF;

  -- Una **referencia** al contenido, nunca el contenido: el contrato de carta
  -- muerta prohibe el payload crudo, y una huella identifica sin transcribir.
  SELECT a.content_sha256 INTO v_digest
    FROM fincilia.source_artifact a WHERE a.artifact_id = v_run.artifact_id;
  SELECT min(a.started_at) INTO v_first
    FROM fincilia.run_attempt a WHERE a.run_id = p_run_id;

  UPDATE fincilia.processing_run r
     SET status = 'failed',
         started_at = coalesce(r.started_at, p_now),
         finished_at = p_now,
         lease_token = NULL, lease_expires_at = NULL,
         error_code = p_reason_code,
         failure_class = p_failure_class
   WHERE r.run_id = p_run_id;

  INSERT INTO fincilia.dead_letter_item (
    dead_letter_id, company_id, work_class, work_id, work_schema_version,
    payload_reference, failure_class, reason_code, attempt_count,
    first_failed_at, last_failed_at, retry_policy_version, owner, resolution_state)
  VALUES (gen_random_uuid(), p_company_id, 'stateless_job', p_run_id, '1',
          coalesce(v_digest, repeat('0', 64)), p_failure_class, p_reason_code,
          v_run.attempt, coalesce(v_first, p_now), p_now, '1', 'Data Engineering',
          -- `unknown_failure_action: fail_closed_requires_triage`: lo que no se
          -- supo clasificar no se reintenta en silencio, se manda a una persona.
          CASE WHEN p_failure_class IN ('unknown', 'requires_human')
               THEN 'requires_human' ELSE 'open' END)
  ON CONFLICT (work_class, work_id) DO NOTHING;

  DELETE FROM fincilia.dispatch_pointer d WHERE d.run_id = p_run_id;
END;
$dlq$;

CREATE FUNCTION fincilia.finish_run(
  p_run_id uuid, p_lease_token uuid, p_result jsonb, p_error_code text,
  p_failure_class text) RETURNS text
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
  IF p_error_code IS NOT NULL AND p_error_code !~ '^[a-z][a-z0-9_]{2,79}$' THEN
    RAISE EXCEPTION 'reason codes are a bounded vocabulary' USING ERRCODE = '22023';
  END IF;
  IF (p_error_code IS NULL) <> (p_failure_class IS NULL) THEN
    RAISE EXCEPTION 'a failure needs both a reason and a class' USING ERRCODE = '22023';
  END IF;
  IF p_failure_class IS NOT NULL
     AND p_failure_class NOT IN ('retryable', 'rate_limited', 'fatal',
                                 'requires_human', 'unknown') THEN
    RAISE EXCEPTION 'unknown failure class' USING ERRCODE = '22023';
  END IF;

  -- Siempre el puntero primero. El otro orden produce interbloqueo con el
  -- reclamo justo cuando un arriendo vence mientras su dueno termina.
  SELECT d.company_id INTO v_company
    FROM fincilia.dispatch_pointer d WHERE d.run_id = p_run_id FOR UPDATE;
  IF NOT FOUND THEN
    -- Sin puntero el trabajo ya es terminal: alguien lo cerro antes.
    RETURN 'stale_lease';
  END IF;
  PERFORM set_config('fincilia.company_id', v_company::text, true);

  SELECT r.* INTO v_run FROM fincilia.processing_run r
   WHERE r.run_id = p_run_id FOR UPDATE;
  IF NOT FOUND THEN
    PERFORM set_config('fincilia.company_id', v_saved, true);
    RETURN 'not_found';
  END IF;

  -- El testigo de arriendo separa a quien esta trabajando de quien **estuvo**
  -- trabajando. Un worker que revive despues de que otro recupero el trabajo no
  -- escribe nada: ni resultado, ni estado, ni puntero.
  IF v_run.status <> 'running'
     OR v_run.lease_token IS DISTINCT FROM p_lease_token
     OR v_run.lease_expires_at <= v_now THEN
    PERFORM set_config('fincilia.company_id', v_saved, true);
    RETURN 'stale_lease';
  END IF;

  UPDATE fincilia.run_attempt a
     SET finished_at = v_now,
         outcome = CASE WHEN p_error_code IS NULL THEN 'succeeded' ELSE 'failed' END,
         failure_class = p_failure_class,
         reason_code = p_error_code
   WHERE a.run_id = p_run_id AND a.lease_token = p_lease_token;

  IF p_error_code IS NULL THEN
    UPDATE fincilia.processing_run r
       SET status = 'succeeded', finished_at = v_now, lease_token = NULL,
           lease_expires_at = NULL, error_code = NULL, failure_class = NULL,
           result = coalesce(p_result, r.result)
     WHERE r.run_id = p_run_id;
    -- Terminal y sin puntero son un solo hecho, en una sola transaccion.
    DELETE FROM fincilia.dispatch_pointer d WHERE d.run_id = p_run_id;
    v_outcome := 'succeeded';

  ELSIF p_failure_class IN ('fatal', 'requires_human') THEN
    -- Un fallo fatal no mejora reintentandolo: gastar intentos solo llegaria al
    -- mismo sitio mas tarde.
    UPDATE fincilia.processing_run r
       SET status = 'failed', finished_at = v_now, lease_token = NULL,
           lease_expires_at = NULL, error_code = p_error_code,
           failure_class = p_failure_class
     WHERE r.run_id = p_run_id;
    DELETE FROM fincilia.dispatch_pointer d WHERE d.run_id = p_run_id;
    v_outcome := 'failed';

  ELSIF v_run.attempt >= v_run.max_attempts THEN
    PERFORM fincilia.send_to_dead_letter(p_run_id, v_company, p_failure_class,
                                         'attempts_exhausted', v_now);
    v_outcome := 'dead_letter';

  ELSE
    -- Reintentable y quedan intentos: vuelve a la cola con espera creciente y el
    -- contador sube una vez, aqui, por intento realmente gastado.
    v_backoff := least(300, 5 * (2 ^ v_run.attempt)::integer);
    UPDATE fincilia.processing_run r
       SET status = 'queued', started_at = NULL, finished_at = NULL,
           lease_token = NULL, lease_expires_at = NULL, claimed_by = NULL,
           error_code = NULL, failure_class = NULL, attempt = r.attempt + 1
     WHERE r.run_id = p_run_id;
    UPDATE fincilia.dispatch_pointer d
       SET available_at = v_now + make_interval(secs => v_backoff)
     WHERE d.run_id = p_run_id;
    v_outcome := 'requeued';
  END IF;

  PERFORM set_config('fincilia.company_id', v_saved, true);
  RETURN v_outcome;
END;
$finish$;

-- --------------------------------------------------------------------------- --
-- 8. Dueno y privilegios de las funciones
-- --------------------------------------------------------------------------- --

-- El dueno **no** es el migrador. El migrador tiene CREATE sobre la base: una
-- funcion `SECURITY DEFINER` suya convertiria cada `EXECUTE` en una escalada
-- hasta el rol que hace DDL. `fincilia_dispatch` no tiene login, no tiene DDL, y
-- tiene exactamente los privilegios de cola que estas cuatro funciones ejercen.
-- PostgreSQL exige que el nuevo propietario tenga CREATE sobre el esquema que
-- contiene el objeto. Se concede para las cuatro sentencias y se retira acto
-- seguido: `fincilia_dispatch` no debe poder crear nada, y el permiso solo hace
-- falta en el instante de ceder la propiedad.
GRANT CREATE ON SCHEMA fincilia TO fincilia_dispatch;

ALTER FUNCTION fincilia.enqueue_processing_run(uuid, uuid, text) OWNER TO fincilia_dispatch;
ALTER FUNCTION fincilia.claim_next_run(text, integer) OWNER TO fincilia_dispatch;
ALTER FUNCTION fincilia.send_to_dead_letter(uuid, uuid, text, text, timestamptz)
  OWNER TO fincilia_dispatch;
ALTER FUNCTION fincilia.finish_run(uuid, uuid, jsonb, text, text) OWNER TO fincilia_dispatch;

REVOKE CREATE ON SCHEMA fincilia FROM fincilia_dispatch;

-- V0001 nunca registro privilegios por defecto sobre FUNCIONES, asi que una
-- funcion nueva es ejecutable por `PUBLIC`. `PUBLIC` incluye a cualquier rol
-- futuro; un `EXECUTE` heredado es justo el privilegio que nadie revisa.
ALTER DEFAULT PRIVILEGES FOR ROLE fincilia_migrator IN SCHEMA fincilia
  REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

-- `SET ROLE` no es adorno. Tras ceder la propiedad, el migrador ya no es dueno de
-- estas funciones, y `NOINHERIT` significa que no adquiere los derechos del rol
-- del que es miembro sin pedirlo. Un REVOKE de quien no es dueno **no falla**:
-- emite un WARNING y no hace nada. La primera version de esta migracion dejo asi
-- las cuatro funciones ejecutables por PUBLIC, y solo lo delato consultar el ACL
-- real. Por eso hay ademas una prueba contra la base que lo comprueba.
SET LOCAL ROLE fincilia_dispatch;

REVOKE ALL PRIVILEGES ON FUNCTION fincilia.enqueue_processing_run(uuid, uuid, text) FROM PUBLIC;
REVOKE ALL PRIVILEGES ON FUNCTION fincilia.claim_next_run(text, integer) FROM PUBLIC;
REVOKE ALL PRIVILEGES ON FUNCTION fincilia.finish_run(uuid, uuid, jsonb, text, text) FROM PUBLIC;
REVOKE ALL PRIVILEGES ON FUNCTION fincilia.send_to_dead_letter(uuid, uuid, text, text, timestamptz) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION fincilia.enqueue_processing_run(uuid, uuid, text) TO fincilia_app;
GRANT EXECUTE ON FUNCTION fincilia.claim_next_run(text, integer) TO fincilia_worker;
GRANT EXECUTE ON FUNCTION fincilia.finish_run(uuid, uuid, jsonb, text, text) TO fincilia_worker;

RESET ROLE;
-- `send_to_dead_letter` no se concede a nadie: solo la llaman las otras dos, y
-- como dueno de ellas es `fincilia_dispatch`, no hace falta EXECUTE externo.

-- --------------------------------------------------------------------------- --
-- 9. Privilegios de tabla de los roles nuevos
-- --------------------------------------------------------------------------- --

-- El dueno de las funciones: exactamente lo que ejercen, ni un verbo mas.
GRANT SELECT, INSERT, UPDATE ON fincilia.processing_run TO fincilia_dispatch;
GRANT SELECT, INSERT, UPDATE, DELETE ON fincilia.dispatch_pointer TO fincilia_dispatch;
GRANT SELECT, INSERT, UPDATE ON fincilia.run_attempt TO fincilia_dispatch;
GRANT SELECT, INSERT ON fincilia.dead_letter_item TO fincilia_dispatch;
GRANT SELECT ON fincilia.source_artifact, fincilia.authorization_version TO fincilia_dispatch;

-- El worker: leer lo que necesita para trabajar y dejar rastro. **Ni un UPDATE**
-- sobre la cola: para eso estan las funciones, con parametros validados.
GRANT SELECT ON fincilia.source_artifact, fincilia.processing_run,
                fincilia.run_attempt, fincilia.dead_letter_item,
                fincilia.schema_history TO fincilia_worker;
GRANT SELECT, INSERT ON fincilia.audit_event TO fincilia_worker;
-- El worker no toca identidad, ni firmas, ni membresias, ni concesiones, ni
-- credenciales. Procesa ficheros; no autoriza a nadie.

-- La API puede leer el historial y la carta muerta para poder explicar por que un
-- documento no tiene perfil. Explicar un fallo es parte del producto.
GRANT SELECT ON fincilia.run_attempt, fincilia.dead_letter_item TO fincilia_app;

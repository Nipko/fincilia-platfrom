-- V0067 (FNC-SMB-001): perfil operativo por empresa y modo de revision.
--
-- ADR-039 secciones 1 a 3. Una empresa `estricto` conserva exactamente la
-- segregacion de funciones de ADR-027, ADR-028 y ADR-035: los mismos rechazos,
-- con los mismos codigos de error y los mismos nombres de restriccion. Una
-- empresa `simple` permite que la misma persona proponga y decida, pero la
-- decision queda marcada `self_reviewed` y nunca se presenta como independiente.
--
-- El perfil se lee siempre desde `fincilia.company` dentro del disparador. El
-- cliente no lo envia y no puede elegir el modo de revision: el disparador lo
-- sobrescribe. `approved_rule` queda reservado para una tarea posterior y hoy se
-- rechaza en toda tabla.
--
-- Empresas existentes quedan en `estricto`. Ninguna guarda de `partial`,
-- `unknown` o `unverified`, ni el bloqueo de periodos cerrados, cambia aqui.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

-- --------------------------------------------------------------------------- --
-- 1. Perfil operativo y su historial append-only
-- --------------------------------------------------------------------------- --

ALTER TABLE fincilia.company
  ADD COLUMN operating_profile text NOT NULL DEFAULT 'estricto'
    CONSTRAINT ck_company_operating_profile
    CHECK (operating_profile IN ('simple', 'estricto'));

CREATE TABLE fincilia.company_operating_profile_change (
  change_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id      uuid NOT NULL REFERENCES fincilia.company(company_id),
  version         integer NOT NULL CHECK (version >= 1),
  from_profile    text NOT NULL CHECK (from_profile IN ('simple', 'estricto')),
  to_profile      text NOT NULL CHECK (to_profile IN ('simple', 'estricto')),
  -- El motivo lo escribe una persona. Es texto acotado; la API recuerda que no
  -- debe contener datos financieros ni personales.
  reason          text NOT NULL CHECK (length(btrim(reason)) BETWEEN 10 AND 500),
  changed_by      uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  changed_at      timestamptz NOT NULL DEFAULT now(),
  audit_event_id  uuid NOT NULL,

  CONSTRAINT uq_operating_profile_change_company UNIQUE (change_id, company_id),
  CONSTRAINT uq_operating_profile_change_version UNIQUE (company_id, version),
  CONSTRAINT fk_operating_profile_change_audit FOREIGN KEY (audit_event_id, company_id)
    REFERENCES fincilia.audit_event(audit_event_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT ck_operating_profile_change_differs CHECK (from_profile <> to_profile)
);

CREATE INDEX idx_operating_profile_change_time
  ON fincilia.company_operating_profile_change (company_id, changed_at DESC, change_id);

COMMENT ON TABLE fincilia.company_operating_profile_change IS
  'Historial append-only de cambios de perfil operativo (ADR-039). Solo el owner '
  'activo de la empresa cambia el perfil; el cambio no reescribe decisiones previas.';

-- Perfil efectivo. Si la fila no es visible bajo la politica vigente se
-- responde `estricto`: el valor seguro nunca relaja una guarda.
CREATE FUNCTION fincilia.company_operating_profile(requested_company_id uuid)
RETURNS text
LANGUAGE sql
STABLE
SET search_path = pg_catalog, fincilia
AS $function$
  SELECT COALESCE(
    (SELECT c.operating_profile FROM fincilia.company c
      WHERE c.company_id = requested_company_id),
    'estricto')
$function$;

REVOKE ALL ON FUNCTION fincilia.company_operating_profile(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.company_operating_profile(uuid)
  TO fincilia_app, fincilia_migrator;

-- Modo de revision derivado. `independent` si los actores difieren;
-- `self_reviewed` solo si coinciden y la empresa es `simple`; NULL si coinciden
-- en `estricto`, que cada guarda convierte en su rechazo historico.
CREATE FUNCTION fincilia.review_mode_for(
  requested_company_id uuid, proposer_id uuid, decider_id uuid
) RETURNS text
LANGUAGE sql
STABLE
SET search_path = pg_catalog, fincilia
AS $function$
  SELECT CASE
    WHEN proposer_id IS NULL OR decider_id IS NULL THEN NULL
    WHEN proposer_id <> decider_id THEN 'independent'
    WHEN fincilia.company_operating_profile(requested_company_id) = 'simple'
      THEN 'self_reviewed'
    ELSE NULL
  END
$function$;

REVOKE ALL ON FUNCTION fincilia.review_mode_for(uuid, uuid, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.review_mode_for(uuid, uuid, uuid)
  TO fincilia_app, fincilia_migrator;

CREATE FUNCTION fincilia.validate_operating_profile_change()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  current_profile text;
  next_version integer;
BEGIN
  PERFORM pg_advisory_xact_lock(hashtextextended(NEW.company_id::text, 39001));

  SELECT c.operating_profile INTO current_profile
  FROM fincilia.company c
  WHERE c.company_id = NEW.company_id
  FOR UPDATE;
  IF current_profile IS NULL THEN
    RAISE EXCEPTION 'company is unavailable' USING ERRCODE = '23503';
  END IF;

  -- El rol se resuelve aqui, no en el cliente: owner activo, persona activa.
  IF NOT EXISTS (
    SELECT 1
    FROM fincilia.company_grant g
    JOIN fincilia.subject s ON s.subject_id = g.subject_id
    WHERE g.company_id = NEW.company_id
      AND g.subject_id = NEW.changed_by
      AND g.company_role = 'owner'
      AND g.revoked_at IS NULL
      AND s.status = 'active'
      AND s.subject_kind = 'person'
  ) THEN
    RAISE EXCEPTION 'only an active company owner may change the operating profile'
      USING ERRCODE = '42501', CONSTRAINT = 'ck_operating_profile_change_owner';
  END IF;

  IF NEW.from_profile <> current_profile THEN
    RAISE EXCEPTION 'operating profile change does not start from the current profile'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_operating_profile_change_current';
  END IF;

  SELECT COALESCE(max(version), 0) + 1 INTO next_version
  FROM fincilia.company_operating_profile_change
  WHERE company_id = NEW.company_id;
  IF NEW.version <> next_version THEN
    RAISE EXCEPTION 'operating profile change version is not next'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_operating_profile_change_version';
  END IF;

  NEW.changed_at := now();
  RETURN NEW;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.validate_operating_profile_change() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.validate_operating_profile_change()
  TO fincilia_app, fincilia_migrator;

CREATE TRIGGER company_operating_profile_change_guard
  BEFORE INSERT ON fincilia.company_operating_profile_change
  FOR EACH ROW EXECUTE FUNCTION fincilia.validate_operating_profile_change();

-- La fila del historial es la causa; la columna de company, su efecto.
CREATE FUNCTION fincilia.apply_operating_profile_change()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
BEGIN
  UPDATE fincilia.company
     SET operating_profile = NEW.to_profile
   WHERE company_id = NEW.company_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'company is unavailable' USING ERRCODE = '23503';
  END IF;
  RETURN NULL;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.apply_operating_profile_change() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.apply_operating_profile_change()
  TO fincilia_app, fincilia_migrator;

CREATE TRIGGER company_operating_profile_change_apply
  AFTER INSERT ON fincilia.company_operating_profile_change
  FOR EACH ROW EXECUTE FUNCTION fincilia.apply_operating_profile_change();

-- Un UPDATE directo sobre company solo puede dejar el perfil en el valor que
-- dice la ultima fila del historial. Asi la unica via real de cambio es una
-- fila validada (owner, perfil actual, version siguiente y auditoria).
CREATE FUNCTION fincilia.guard_company_operating_profile()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  latest_profile text;
BEGIN
  IF NEW.operating_profile IS NOT DISTINCT FROM OLD.operating_profile THEN
    RETURN NEW;
  END IF;
  SELECT to_profile INTO latest_profile
  FROM fincilia.company_operating_profile_change
  WHERE company_id = NEW.company_id
  ORDER BY version DESC
  LIMIT 1;
  IF latest_profile IS NULL OR latest_profile <> NEW.operating_profile THEN
    RAISE EXCEPTION 'operating profile changes only through its append-only history'
      USING ERRCODE = '42501', CONSTRAINT = 'ck_company_operating_profile_history';
  END IF;
  RETURN NEW;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.guard_company_operating_profile() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.guard_company_operating_profile()
  TO fincilia_app, fincilia_migrator;

CREATE TRIGGER company_operating_profile_guard
  BEFORE UPDATE OF operating_profile ON fincilia.company
  FOR EACH ROW EXECUTE FUNCTION fincilia.guard_company_operating_profile();

CREATE FUNCTION fincilia.reject_operating_profile_change_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
BEGIN
  RAISE EXCEPTION 'operating profile history is append-only' USING ERRCODE = '55000';
END
$function$;

REVOKE ALL ON FUNCTION fincilia.reject_operating_profile_change_mutation() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.reject_operating_profile_change_mutation()
  TO fincilia_app, fincilia_migrator;

CREATE TRIGGER company_operating_profile_change_append_only
  BEFORE UPDATE OR DELETE ON fincilia.company_operating_profile_change
  FOR EACH ROW EXECUTE FUNCTION fincilia.reject_operating_profile_change_mutation();

ALTER TABLE fincilia.company_operating_profile_change ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.company_operating_profile_change FORCE ROW LEVEL SECURITY;
CREATE POLICY company_operating_profile_change_isolation
  ON fincilia.company_operating_profile_change
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

REVOKE ALL ON fincilia.company_operating_profile_change FROM PUBLIC;
GRANT SELECT, INSERT ON fincilia.company_operating_profile_change TO fincilia_app;
REVOKE UPDATE, DELETE ON fincilia.company_operating_profile_change FROM fincilia_app;
REVOKE ALL ON fincilia.company_operating_profile_change FROM fincilia_worker;

-- --------------------------------------------------------------------------- --
-- 2. Columna review_mode en cada decision con segregacion de funciones
-- --------------------------------------------------------------------------- --

ALTER TABLE fincilia.match_decision
  ADD COLUMN review_mode text NOT NULL DEFAULT 'independent'
    CONSTRAINT ck_match_decision_review_mode
    CHECK (review_mode IN ('independent', 'self_reviewed', 'approved_rule'));
ALTER TABLE fincilia.field_overlay_review
  ADD COLUMN review_mode text NOT NULL DEFAULT 'independent'
    CONSTRAINT ck_field_overlay_review_mode
    CHECK (review_mode IN ('independent', 'self_reviewed', 'approved_rule'));
ALTER TABLE fincilia.lineage_row_override
  ADD COLUMN review_mode text NOT NULL DEFAULT 'independent'
    CONSTRAINT ck_override_review_mode
    CHECK (review_mode IN ('independent', 'self_reviewed', 'approved_rule'));
ALTER TABLE fincilia.dataset_version
  ADD COLUMN review_mode text NOT NULL DEFAULT 'independent'
    CONSTRAINT ck_dataset_review_mode
    CHECK (review_mode IN ('independent', 'self_reviewed', 'approved_rule'));
ALTER TABLE fincilia.reconciling_item
  ADD COLUMN review_mode text NOT NULL DEFAULT 'independent'
    CONSTRAINT ck_item_review_mode
    CHECK (review_mode IN ('independent', 'self_reviewed', 'approved_rule'));
ALTER TABLE fincilia.close_review_packet
  ADD COLUMN review_mode text NOT NULL DEFAULT 'independent'
    CONSTRAINT ck_close_review_packet_review_mode
    CHECK (review_mode IN ('independent', 'self_reviewed', 'approved_rule'));
ALTER TABLE fincilia.close_review_decision
  ADD COLUMN review_mode text NOT NULL DEFAULT 'independent'
    CONSTRAINT ck_close_review_decision_review_mode
    CHECK (review_mode IN ('independent', 'self_reviewed', 'approved_rule'));
ALTER TABLE fincilia.accounting_period_close
  ADD COLUMN review_mode text NOT NULL DEFAULT 'independent'
    CONSTRAINT ck_accounting_period_close_review_mode
    CHECK (review_mode IN ('independent', 'self_reviewed', 'approved_rule'));
ALTER TABLE fincilia.accounting_period_close
  ADD COLUMN certification text NOT NULL DEFAULT 'certified'
    CONSTRAINT ck_accounting_period_close_certification
    CHECK (certification IN ('self_reviewed', 'certified'));
ALTER TABLE fincilia.accounting_period_reopen_decision
  ADD COLUMN review_mode text NOT NULL DEFAULT 'independent'
    CONSTRAINT ck_period_reopen_decision_review_mode
    CHECK (review_mode IN ('independent', 'self_reviewed', 'approved_rule'));

-- --------------------------------------------------------------------------- --
-- 3. Restricciones CHECK de segregacion
-- --------------------------------------------------------------------------- --

-- Cada CHECK conserva su nombre. En `estricto` el disparador deja
-- `independent` cuando los actores coinciden, y la misma restriccion de siempre
-- rechaza la fila con el mismo mensaje y SQLSTATE 23514. En `simple` el
-- disparador fija `self_reviewed`, y la restriccion exige que ese modo vaya
-- siempre con actores coincidentes: nunca hay autorrevision disfrazada.

ALTER TABLE fincilia.lineage_row_override
  DROP CONSTRAINT ck_override_segregation;
ALTER TABLE fincilia.lineage_row_override
  ADD CONSTRAINT ck_override_segregation CHECK (
    approved_by IS NULL
    OR (approved_by <> created_by AND review_mode = 'independent')
    OR (approved_by = created_by AND review_mode = 'self_reviewed'));

ALTER TABLE fincilia.dataset_version
  DROP CONSTRAINT ck_dataset_publisher_is_not_author;
ALTER TABLE fincilia.dataset_version
  ADD CONSTRAINT ck_dataset_publisher_is_not_author CHECK (
    published_by IS NULL
    OR (published_by <> prepared_by AND review_mode = 'independent')
    OR (published_by = prepared_by AND review_mode = 'self_reviewed'));

ALTER TABLE fincilia.reconciling_item
  DROP CONSTRAINT ck_item_approval;
ALTER TABLE fincilia.reconciling_item
  ADD CONSTRAINT ck_item_approval CHECK (
    (state = 'proposed' AND approved_by IS NULL AND approved_at IS NULL)
    OR (state IN ('confirmed', 'rejected', 'reversed')
        AND approved_by IS NOT NULL AND approved_at IS NOT NULL
        AND ((approved_by <> prepared_by AND review_mode = 'independent')
             OR (approved_by = prepared_by AND review_mode = 'self_reviewed'))));

ALTER TABLE fincilia.close_review_packet
  DROP CONSTRAINT ck_close_review_packet_sod;
ALTER TABLE fincilia.close_review_packet
  ADD CONSTRAINT ck_close_review_packet_sod CHECK (
    (prepared_by <> assigned_reviewer_id AND review_mode = 'independent')
    OR (prepared_by = assigned_reviewer_id AND review_mode = 'self_reviewed'));

-- Disparador generico para las tablas cuya segregacion vive en un CHECK.
-- TG_ARGV[0] es la columna de quien propone y TG_ARGV[1] la de quien decide.
-- En un UPDATE que no cambia al decisor el modo no se recalcula: un cambio de
-- perfil posterior no reescribe decisiones previas.
CREATE FUNCTION fincilia.assign_review_mode()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  proposer_id uuid;
  decider_id uuid;
BEGIN
  IF TG_OP = 'UPDATE'
     AND (to_jsonb(OLD)->>TG_ARGV[1]) IS NOT DISTINCT FROM (to_jsonb(NEW)->>TG_ARGV[1]) THEN
    NEW.review_mode := OLD.review_mode;
    RETURN NEW;
  END IF;
  IF NEW.review_mode = 'approved_rule' THEN
    RAISE EXCEPTION 'approved_rule review mode is reserved for approved rules'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_review_mode_reserved';
  END IF;
  proposer_id := (to_jsonb(NEW)->>TG_ARGV[0])::uuid;
  decider_id := (to_jsonb(NEW)->>TG_ARGV[1])::uuid;
  IF decider_id IS NULL THEN
    NEW.review_mode := 'independent';
    RETURN NEW;
  END IF;
  NEW.review_mode := COALESCE(
    fincilia.review_mode_for(NEW.company_id, proposer_id, decider_id),
    'independent');
  RETURN NEW;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.assign_review_mode() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.assign_review_mode()
  TO fincilia_app, fincilia_migrator;

CREATE TRIGGER lineage_row_override_review_mode
  BEFORE INSERT OR UPDATE ON fincilia.lineage_row_override
  FOR EACH ROW EXECUTE FUNCTION fincilia.assign_review_mode('created_by', 'approved_by');
CREATE TRIGGER dataset_version_review_mode
  BEFORE INSERT OR UPDATE ON fincilia.dataset_version
  FOR EACH ROW EXECUTE FUNCTION fincilia.assign_review_mode('prepared_by', 'published_by');
CREATE TRIGGER reconciling_item_review_mode
  BEFORE INSERT ON fincilia.reconciling_item
  FOR EACH ROW EXECUTE FUNCTION fincilia.assign_review_mode('prepared_by', 'approved_by');
CREATE TRIGGER close_review_packet_review_mode
  BEFORE INSERT ON fincilia.close_review_packet
  FOR EACH ROW EXECUTE FUNCTION fincilia.assign_review_mode(
    'prepared_by', 'assigned_reviewer_id');

-- --------------------------------------------------------------------------- --
-- 4. Disparadores de segregacion reescritos
-- --------------------------------------------------------------------------- --

-- Cruce 1:1 (V0017). Rechazar sigue permitido al proponente en ambos perfiles,
-- como hasta hoy, pero queda marcado `self_reviewed`.
CREATE OR REPLACE FUNCTION fincilia.enforce_match_decision_sod()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  author_id uuid;
  expected_left uuid;
  expected_right uuid;
  mode text;
BEGIN
  SELECT proposed_by, left_movement_id, right_movement_id
    INTO author_id, expected_left, expected_right
  FROM fincilia.match_candidate
  WHERE candidate_id = NEW.candidate_id AND company_id = NEW.company_id;

  IF author_id IS NULL THEN
    RAISE EXCEPTION 'candidate unavailable' USING ERRCODE = '23503';
  END IF;
  IF NEW.review_mode = 'approved_rule' THEN
    RAISE EXCEPTION 'approved_rule review mode is reserved for approved rules'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_review_mode_reserved';
  END IF;
  mode := fincilia.review_mode_for(NEW.company_id, author_id, NEW.decided_by);
  IF NEW.decision = 'confirmed' AND mode IS NULL THEN
    RAISE EXCEPTION 'segregation of duties: proposer cannot confirm'
      USING ERRCODE = '42501';
  END IF;
  NEW.review_mode := COALESCE(mode, 'self_reviewed');
  IF NEW.evidence_refs <> jsonb_build_array(
       jsonb_build_object('kind', 'movement', 'ref', expected_left::text),
       jsonb_build_object('kind', 'movement', 'ref', expected_right::text)) THEN
    RAISE EXCEPTION 'decision evidence must name the ordered candidate pair'
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END
$function$;

-- Correcciones tipadas (V0016).
CREATE OR REPLACE FUNCTION fincilia.field_overlay_review_enforces_sod()
RETURNS trigger
LANGUAGE plpgsql
AS $body$
DECLARE
  v_author uuid;
  v_mode text;
BEGIN
  SELECT created_by INTO v_author
    FROM fincilia.field_overlay
   WHERE overlay_id = NEW.overlay_id AND company_id = NEW.company_id;
  IF v_author IS NULL THEN
    RAISE EXCEPTION 'field overlay is not available in this company'
      USING ERRCODE = '23503';
  END IF;
  IF NEW.review_mode = 'approved_rule' THEN
    RAISE EXCEPTION 'approved_rule review mode is reserved for approved rules'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_review_mode_reserved';
  END IF;
  v_mode := fincilia.review_mode_for(NEW.company_id, v_author, NEW.reviewer_id);
  IF v_mode IS NULL THEN
    RAISE EXCEPTION 'field overlay author cannot review their own proposal'
      USING ERRCODE = '23514';
  END IF;
  NEW.review_mode := v_mode;
  RETURN NEW;
END;
$body$;

-- Decision del expediente de cierre (V0034).
CREATE OR REPLACE FUNCTION fincilia.validate_close_review_decision()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  packet fincilia.close_review_packet%ROWTYPE;
  mode text;
BEGIN
  SELECT * INTO packet FROM fincilia.close_review_packet
  WHERE packet_id = NEW.packet_id AND company_id = NEW.company_id;
  IF packet.packet_id IS NULL THEN
    RAISE EXCEPTION 'close review packet is unavailable' USING ERRCODE = '23503';
  END IF;
  IF NEW.review_mode = 'approved_rule' THEN
    RAISE EXCEPTION 'approved_rule review mode is reserved for approved rules'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_review_mode_reserved';
  END IF;
  mode := fincilia.review_mode_for(NEW.company_id, packet.prepared_by, NEW.decided_by);
  IF NEW.decided_by <> packet.assigned_reviewer_id
     OR mode IS NULL
     OR NOT fincilia.is_close_reviewer_eligible(NEW.company_id, NEW.decided_by) THEN
    RAISE EXCEPTION 'segregation of duties: assigned reviewer required'
      USING ERRCODE = '42501';
  END IF;
  NEW.review_mode := mode;
  IF NEW.observed_manifest_digest <> packet.manifest_digest THEN
    RAISE EXCEPTION 'reviewed manifest digest differs from the packet'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_close_review_digest';
  END IF;
  IF NEW.decision = 'evidence_reviewed' AND (
       packet.diagnostic_status <> 'ready_for_review'
       OR NEW.reason_code <> 'controls_reviewed') THEN
    RAISE EXCEPTION 'blocked evidence cannot be marked reviewed'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_close_review_positive';
  END IF;
  IF NEW.decision = 'changes_requested' AND NEW.reason_code = 'controls_reviewed' THEN
    RAISE EXCEPTION 'changes requested requires a blocking reason'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_close_review_negative';
  END IF;
  RETURN NEW;
END
$function$;

-- Decision de reapertura (V0046).
CREATE OR REPLACE FUNCTION fincilia.validate_accounting_period_reopen_decision()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  source_request fincilia.accounting_period_reopen_request%ROWTYPE;
  mode text;
BEGIN
  PERFORM pg_advisory_xact_lock(hashtextextended(NEW.company_id::text, 35006));
  SELECT * INTO source_request FROM fincilia.accounting_period_reopen_request
  WHERE request_id = NEW.request_id AND company_id = NEW.company_id;
  IF NEW.review_mode = 'approved_rule' THEN
    RAISE EXCEPTION 'approved_rule review mode is reserved for approved rules'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_review_mode_reserved';
  END IF;
  mode := fincilia.review_mode_for(
    NEW.company_id, source_request.requested_by, NEW.decided_by);
  IF source_request.request_id IS NULL OR mode IS NULL THEN
    RAISE EXCEPTION 'reopen decision requires a different person'
      USING ERRCODE = '42501', CONSTRAINT = 'ck_period_reopen_sod';
  END IF;
  NEW.review_mode := mode;
  IF NEW.decision = 'approved'
     AND NEW.reason_code <> 'documented_basis_confirmed' THEN
    RAISE EXCEPTION 'approved reopen requires documented basis'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_period_reopen_positive';
  END IF;
  IF NEW.decision = 'rejected'
     AND NEW.reason_code = 'documented_basis_confirmed' THEN
    RAISE EXCEPTION 'rejected reopen requires a refusal reason'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_period_reopen_negative';
  END IF;
  RETURN NEW;
END
$function$;

-- Cierre del periodo (V0046). En `estricto` quien cierra sigue siendo el
-- revisor asignado y distinto del preparador; el cierre nace `certified`. En
-- `simple` el owner puede ser preparador, revisor y quien cierra: el cierre
-- nace `self_reviewed` y espera una certificacion independiente posterior.
CREATE OR REPLACE FUNCTION fincilia.validate_accounting_period_close()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  packet fincilia.close_review_packet%ROWTYPE;
  reviewed_by uuid;
  next_version integer;
  item jsonb;
  mode text;
BEGIN
  PERFORM pg_advisory_xact_lock(hashtextextended(NEW.company_id::text, 35006));

  SELECT * INTO packet
  FROM fincilia.close_review_packet
  WHERE packet_id = NEW.packet_id AND company_id = NEW.company_id;

  SELECT d.decided_by INTO reviewed_by
  FROM fincilia.close_review_decision d
  WHERE d.packet_id = NEW.packet_id
    AND d.company_id = NEW.company_id
    AND d.decision = 'evidence_reviewed'
    AND d.observed_manifest_digest = NEW.observed_manifest_digest;

  IF NEW.review_mode = 'approved_rule' THEN
    RAISE EXCEPTION 'approved_rule review mode is reserved for approved rules'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_review_mode_reserved';
  END IF;
  mode := fincilia.review_mode_for(NEW.company_id, packet.prepared_by, NEW.closed_by);

  IF packet.packet_id IS NULL
     OR packet.period_start <> NEW.period_start
     OR packet.period_end <> NEW.period_end
     OR packet.manifest_digest <> NEW.observed_manifest_digest
     OR reviewed_by IS NULL
     OR reviewed_by <> NEW.closed_by
     OR mode IS NULL THEN
    RAISE EXCEPTION 'period close requires the assigned reviewed packet'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_period_close_reviewed_packet';
  END IF;
  NEW.review_mode := mode;
  NEW.certification := CASE WHEN mode = 'independent'
                            THEN 'certified' ELSE 'self_reviewed' END;

  IF EXISTS (
    SELECT 1 FROM fincilia.close_review_packet newer
    WHERE newer.company_id = NEW.company_id
      AND newer.period_start = NEW.period_start
      AND newer.period_end = NEW.period_end
      AND newer.version > packet.version
  ) THEN
    RAISE EXCEPTION 'a newer close review packet exists'
      USING ERRCODE = '40001', CONSTRAINT = 'ck_period_close_latest_packet';
  END IF;

  IF fincilia.accounting_period_is_closed(
      NEW.company_id, NEW.period_start, NEW.period_end) THEN
    RAISE EXCEPTION 'accounting period already closed or overlaps an active close'
      USING ERRCODE = '23P01', CONSTRAINT = 'ck_period_close_no_overlap';
  END IF;

  SELECT COALESCE(max(version), 0) + 1 INTO next_version
  FROM fincilia.accounting_period_close
  WHERE company_id = NEW.company_id
    AND period_start = NEW.period_start
    AND period_end = NEW.period_end;
  IF NEW.version <> next_version THEN
    RAISE EXCEPTION 'accounting period close version is not next'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_period_close_version';
  END IF;

  IF jsonb_typeof(NEW.snapshot) <> 'object'
     OR (SELECT count(*) FROM jsonb_object_keys(NEW.snapshot)) <> 7
     OR NOT NEW.snapshot ?& ARRAY[
       'schema_version', 'packet_id', 'packet_version', 'manifest_digest',
       'controls', 'sources', 'accounts']
     OR NEW.snapshot->>'schema_version' <> NEW.snapshot_schema_version
     OR NEW.snapshot->>'packet_id' <> NEW.packet_id::text
     OR (NEW.snapshot->>'packet_version')::integer <> packet.version
     OR NEW.snapshot->>'manifest_digest' <> NEW.observed_manifest_digest
     OR jsonb_typeof(NEW.snapshot->'controls') <> 'array'
     OR jsonb_typeof(NEW.snapshot->'sources') <> 'array'
     OR jsonb_typeof(NEW.snapshot->'accounts') <> 'array'
     OR jsonb_array_length(NEW.snapshot->'controls') <> 16
     OR jsonb_array_length(NEW.snapshot->'sources') = 0
     OR jsonb_array_length(NEW.snapshot->'accounts') = 0 THEN
    RAISE EXCEPTION 'accounting close snapshot envelope is invalid'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_period_close_snapshot';
  END IF;

  IF (SELECT array_agg(value->>'code' ORDER BY value->>'code')
      FROM jsonb_array_elements(NEW.snapshot->'controls')) <>
     ARRAY[
       'account_balances', 'accounting_dates', 'complete_lineage',
       'completeness_assessments', 'dataset_evidence', 'expectations_satisfied',
       'expected_sources', 'pending_corrections', 'product_close',
       'published_datasets', 'quality_alerts', 'reconciliation_reviews',
       'reconciliation_statement_lineage', 'reconciliation_statements',
       'rejected_rows', 'verified_completeness'] THEN
    RAISE EXCEPTION 'accounting close control set is incomplete'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_period_close_control_set';
  END IF;

  FOR item IN SELECT value FROM jsonb_array_elements(NEW.snapshot->'controls')
  LOOP
    IF (item->>'code' = 'product_close' AND item->>'state' <> 'unavailable')
       OR (item->>'code' <> 'product_close' AND item->>'state' <> 'pass') THEN
      RAISE EXCEPTION 'accounting close contains a blocking control'
        USING ERRCODE = '23514', CONSTRAINT = 'ck_period_close_controls_pass';
    END IF;
  END LOOP;

  FOR item IN SELECT value FROM jsonb_array_elements(NEW.snapshot->'sources')
  LOOP
    IF item->>'expectation_state' <> 'satisfied'
       OR item->>'dataset_state' <> 'published'
       OR item->>'completeness_state' <> 'verified'
       OR item->>'lineage_state' <> 'complete'
       OR (item->>'rejected_count')::integer <> 0 THEN
      RAISE EXCEPTION 'accounting close source is not eligible'
        USING ERRCODE = '23514', CONSTRAINT = 'ck_period_close_source_eligible';
    END IF;
  END LOOP;

  FOR item IN SELECT value FROM jsonb_array_elements(NEW.snapshot->'accounts')
  LOOP
    IF jsonb_typeof(item) <> 'object'
       OR NOT item ?& ARRAY['financial_account_id', 'statement_id',
                            'statement_version', 'statement_state',
                            'statement_lineage_state', 'coverage_state'] THEN
      RAISE EXCEPTION 'accounting close account reference is invalid'
        USING ERRCODE = '23514', CONSTRAINT = 'ck_period_close_account_ref';
    END IF;
    IF (item->>'statement_id') IS NULL
       OR (item->>'statement_version') IS NULL
       OR item->>'statement_state' <> 'balanced'
       OR item->>'statement_lineage_state' <> 'complete'
       OR item->>'coverage_state' <> 'covered' THEN
      RAISE EXCEPTION 'accounting close account is not reconciled'
        USING ERRCODE = '23514', CONSTRAINT = 'ck_period_close_account_eligible';
    END IF;
  END LOOP;
  RETURN NEW;
END
$function$;

-- --------------------------------------------------------------------------- --
-- 5. Certificacion posterior de un cierre autorrevisado
-- --------------------------------------------------------------------------- --

-- La certificacion es una fila nueva: el cierre no se muta nunca. Un cierre
-- queda certificado si nacio `certified` o si tiene esta fila.
CREATE TABLE fincilia.accounting_period_close_certification (
  certification_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id               uuid NOT NULL REFERENCES fincilia.company(company_id),
  close_id                 uuid NOT NULL,
  observed_snapshot_digest char(64) NOT NULL CHECK (
                             observed_snapshot_digest ~ '^[0-9a-f]{64}$'),
  certified_by             uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  certified_at             timestamptz NOT NULL DEFAULT now(),
  audit_event_id           uuid NOT NULL,

  CONSTRAINT uq_close_certification_company UNIQUE (certification_id, company_id),
  CONSTRAINT uq_close_certification_close UNIQUE (close_id),
  CONSTRAINT fk_close_certification_close FOREIGN KEY (close_id, company_id)
    REFERENCES fincilia.accounting_period_close(close_id, company_id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_close_certification_audit FOREIGN KEY (audit_event_id, company_id)
    REFERENCES fincilia.audit_event(audit_event_id, company_id)
    ON DELETE RESTRICT
);

CREATE INDEX idx_close_certification_time
  ON fincilia.accounting_period_close_certification
  (company_id, certified_at DESC, certification_id);

CREATE FUNCTION fincilia.validate_accounting_period_close_certification()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  source_close fincilia.accounting_period_close%ROWTYPE;
  preparer_id uuid;
BEGIN
  PERFORM pg_advisory_xact_lock(hashtextextended(NEW.company_id::text, 35006));
  SELECT * INTO source_close FROM fincilia.accounting_period_close
  WHERE close_id = NEW.close_id AND company_id = NEW.company_id;
  IF source_close.close_id IS NULL THEN
    RAISE EXCEPTION 'accounting close is unavailable' USING ERRCODE = '23503';
  END IF;
  SELECT prepared_by INTO preparer_id FROM fincilia.close_review_packet
  WHERE packet_id = source_close.packet_id AND company_id = NEW.company_id;

  IF source_close.certification <> 'self_reviewed' THEN
    RAISE EXCEPTION 'only a self-reviewed close awaits certification'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_close_certification_pending';
  END IF;
  IF EXISTS (
    SELECT 1
    FROM fincilia.accounting_period_reopen_request r
    JOIN fincilia.accounting_period_reopen_decision d
      ON d.request_id = r.request_id AND d.company_id = r.company_id
    WHERE r.close_id = NEW.close_id
      AND r.company_id = NEW.company_id
      AND d.decision = 'approved'
  ) THEN
    RAISE EXCEPTION 'a reopened close cannot be certified'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_close_certification_active';
  END IF;
  IF NEW.observed_snapshot_digest <> source_close.snapshot_digest THEN
    RAISE EXCEPTION 'certified snapshot digest differs from the close'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_close_certification_digest';
  END IF;
  IF NEW.certified_by = source_close.closed_by
     OR preparer_id IS NULL
     OR NEW.certified_by = preparer_id
     OR NOT fincilia.is_close_reviewer_eligible(NEW.company_id, NEW.certified_by) THEN
    RAISE EXCEPTION 'segregation of duties: an independent eligible certifier is required'
      USING ERRCODE = '42501', CONSTRAINT = 'ck_close_certification_sod';
  END IF;
  NEW.certified_at := now();
  RETURN NEW;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.validate_accounting_period_close_certification()
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.validate_accounting_period_close_certification()
  TO fincilia_app, fincilia_migrator;

CREATE TRIGGER accounting_period_close_certification_guard
  BEFORE INSERT ON fincilia.accounting_period_close_certification
  FOR EACH ROW EXECUTE FUNCTION fincilia.validate_accounting_period_close_certification();
CREATE TRIGGER accounting_period_close_certification_append_only
  BEFORE UPDATE OR DELETE ON fincilia.accounting_period_close_certification
  FOR EACH ROW EXECUTE FUNCTION fincilia.reject_accounting_period_mutation();

ALTER TABLE fincilia.accounting_period_close_certification ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.accounting_period_close_certification FORCE ROW LEVEL SECURITY;
CREATE POLICY accounting_period_close_certification_isolation
  ON fincilia.accounting_period_close_certification
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

REVOKE ALL ON fincilia.accounting_period_close_certification FROM PUBLIC;
GRANT SELECT, INSERT ON fincilia.accounting_period_close_certification TO fincilia_app;
REVOKE UPDATE, DELETE ON fincilia.accounting_period_close_certification
  FROM fincilia_app;
REVOKE ALL ON fincilia.accounting_period_close_certification FROM fincilia_worker;

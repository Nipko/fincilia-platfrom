-- V0071 (FNC-SMB-006): cadencia de carga del extracto y recordatorios en la app.
--
-- ADR-039 (modo pyme) y ADR-037 (canales externos desactivados). Una pyme
-- responde una sola pregunta, «¿Cada cuanto subes tu extracto?», y Fincilia le
-- recuerda dentro de la aplicacion cuando el periodo vigente no tiene carga.
--
-- 1. La cadencia vive en un historial append-only por empresa. Solo el owner
--    activo la cambia; cada fila nombra su evento de auditoria. La cadencia
--    vigente es la ultima version: nada se actualiza ni se borra.
-- 2. El recordatorio reutiliza `notification_intent` + `notification_delivery`
--    con una plantilla nueva. La entrega por correo nace `suppressed` con el
--    motivo honesto `in_app_only`: ningun mensaje sale de Fincilia. Cuando
--    ADR-037 apruebe un adaptador, una migracion posterior y la API decidiran
--    si esta plantilla puede encolarse; hoy no puede.
--
-- No hay importes, cuentas, documentos ni identificadores fiscales en el
-- recordatorio: el allowlist de `render_context` de V0049 sigue vigente.
-- Solo datos sinteticos (DRG-00).

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

-- --------------------------------------------------------------------------- --
-- 1. Historial de cadencia
-- --------------------------------------------------------------------------- --

CREATE TABLE fincilia.company_upload_schedule_change (
  change_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id      uuid NOT NULL REFERENCES fincilia.company(company_id),
  version         integer NOT NULL CHECK (version >= 1),
  cadence         text NOT NULL CHECK (cadence IN ('weekly', 'biweekly', 'monthly')),
  changed_by      uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  changed_at      timestamptz NOT NULL DEFAULT now(),
  audit_event_id  uuid NOT NULL,

  CONSTRAINT uq_upload_schedule_change_company UNIQUE (change_id, company_id),
  CONSTRAINT uq_upload_schedule_change_version UNIQUE (company_id, version),
  CONSTRAINT fk_upload_schedule_change_audit FOREIGN KEY (audit_event_id, company_id)
    REFERENCES fincilia.audit_event(audit_event_id, company_id) ON DELETE RESTRICT
);

CREATE INDEX idx_upload_schedule_change_time
  ON fincilia.company_upload_schedule_change (company_id, changed_at DESC, change_id);

COMMENT ON TABLE fincilia.company_upload_schedule_change IS
  'Historial append-only de la cadencia de carga del extracto (FNC-SMB-006). '
  'Solo el owner activo la cambia; la vigente es la ultima version.';

-- Cadencia vigente bajo la politica de la sesion. Invisible o ausente: NULL,
-- que la API presenta como «sin configurar» y nunca convierte en un recordatorio.
CREATE FUNCTION fincilia.company_upload_cadence(requested_company_id uuid)
RETURNS text
LANGUAGE sql
STABLE
SET search_path = pg_catalog, fincilia
AS $function$
  SELECT h.cadence FROM fincilia.company_upload_schedule_change h
  WHERE h.company_id = requested_company_id
  ORDER BY h.version DESC
  LIMIT 1
$function$;

REVOKE ALL ON FUNCTION fincilia.company_upload_cadence(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.company_upload_cadence(uuid)
  TO fincilia_app, fincilia_migrator;

-- El rol se resuelve aqui, no en el cliente: owner activo y persona activa,
-- version siguiente y una cadencia distinta de la vigente.
CREATE FUNCTION fincilia.validate_upload_schedule_change()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  next_version integer;
  current_cadence text;
BEGIN
  PERFORM pg_advisory_xact_lock(hashtextextended(NEW.company_id::text, 39006));

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
    RAISE EXCEPTION 'only an active company owner may change the upload schedule'
      USING ERRCODE = '42501', CONSTRAINT = 'ck_upload_schedule_change_owner';
  END IF;

  SELECT COALESCE(max(h.version), 0) + 1 INTO next_version
  FROM fincilia.company_upload_schedule_change h
  WHERE h.company_id = NEW.company_id;
  IF NEW.version <> next_version THEN
    RAISE EXCEPTION 'upload schedule change version is not next'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_upload_schedule_change_version';
  END IF;

  current_cadence := fincilia.company_upload_cadence(NEW.company_id);
  IF current_cadence IS NOT DISTINCT FROM NEW.cadence THEN
    RAISE EXCEPTION 'upload schedule change must differ from the current cadence'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_upload_schedule_change_differs';
  END IF;

  NEW.changed_at := now();
  RETURN NEW;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.validate_upload_schedule_change() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.validate_upload_schedule_change()
  TO fincilia_app, fincilia_migrator;

CREATE TRIGGER company_upload_schedule_change_guard
  BEFORE INSERT ON fincilia.company_upload_schedule_change
  FOR EACH ROW EXECUTE FUNCTION fincilia.validate_upload_schedule_change();

CREATE FUNCTION fincilia.reject_upload_schedule_change_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
BEGIN
  RAISE EXCEPTION 'upload schedule history is append-only' USING ERRCODE = '55000';
END
$function$;

REVOKE ALL ON FUNCTION fincilia.reject_upload_schedule_change_mutation() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.reject_upload_schedule_change_mutation()
  TO fincilia_app, fincilia_migrator;

CREATE TRIGGER company_upload_schedule_change_append_only
  BEFORE UPDATE OR DELETE ON fincilia.company_upload_schedule_change
  FOR EACH ROW EXECUTE FUNCTION fincilia.reject_upload_schedule_change_mutation();

ALTER TABLE fincilia.company_upload_schedule_change ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.company_upload_schedule_change FORCE ROW LEVEL SECURITY;
CREATE POLICY company_upload_schedule_change_isolation
  ON fincilia.company_upload_schedule_change
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

REVOKE ALL ON fincilia.company_upload_schedule_change FROM PUBLIC;
GRANT SELECT, INSERT ON fincilia.company_upload_schedule_change TO fincilia_app;
REVOKE UPDATE, DELETE ON fincilia.company_upload_schedule_change FROM fincilia_app;
REVOKE ALL ON fincilia.company_upload_schedule_change FROM fincilia_worker;

-- --------------------------------------------------------------------------- --
-- 2. Recordatorio en la app con el mecanismo existente
-- --------------------------------------------------------------------------- --

ALTER TABLE fincilia.notification_intent
  DROP CONSTRAINT notification_intent_template_code_check;
ALTER TABLE fincilia.notification_intent
  ADD CONSTRAINT ck_notification_intent_template_code CHECK (template_code IN (
    'period_due_soon', 'period_due_today', 'period_in_grace', 'period_overdue',
    'statement_upload_due'));

-- `in_app_only`: el recordatorio existe dentro de Fincilia y el canal externo
-- quedo suprimido por diseno, no por un fallo ni por una baja del usuario.
ALTER TABLE fincilia.notification_delivery
  DROP CONSTRAINT ck_notification_delivery_suppression_reason;
ALTER TABLE fincilia.notification_delivery
  ADD CONSTRAINT ck_notification_delivery_suppression_reason CHECK (
    suppression_reason IS NULL OR suppression_reason IN (
      'user_opt_out', 'adapter_unconfigured', 'destination_unavailable',
      'hard_bounce', 'provider_complaint', 'in_app_only'));

-- Una plantilla en la app nunca se encola para un canal externo. Si un
-- adaptador se aprueba (ADR-037), esta guarda se revisa en una migracion nueva.
-- ADD COLUMN con DEFAULT constante: sin reescritura de la tabla.
ALTER TABLE fincilia.notification_delivery
  ADD COLUMN in_app_only boolean NOT NULL DEFAULT false;
ALTER TABLE fincilia.notification_delivery
  ADD CONSTRAINT ck_notification_delivery_in_app_only CHECK (
    NOT in_app_only
    OR (status = 'suppressed' AND suppression_reason = 'in_app_only'));

CREATE FUNCTION fincilia.enforce_in_app_only_delivery()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
BEGIN
  IF EXISTS (
    SELECT 1 FROM fincilia.notification_intent i
    WHERE i.intent_id = NEW.intent_id
      AND i.company_id = NEW.company_id
      AND i.template_code = 'statement_upload_due'
  ) AND NOT NEW.in_app_only THEN
    RAISE EXCEPTION 'statement upload reminders are in-app only'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_notification_delivery_in_app_only';
  END IF;
  RETURN NEW;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.enforce_in_app_only_delivery() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.enforce_in_app_only_delivery()
  TO fincilia_app, fincilia_migrator;

-- Solo en INSERT: `fincilia_app` no puede actualizar entregas y el CHECK de
-- arriba impide que una fila `in_app_only` cambie a cualquier otro estado.
CREATE TRIGGER notification_delivery_in_app_only
  BEFORE INSERT ON fincilia.notification_delivery
  FOR EACH ROW EXECUTE FUNCTION fincilia.enforce_in_app_only_delivery();

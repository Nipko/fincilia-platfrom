-- V0069 (FNC-SMB-003): candidatos con tolerancia explicita y reglas aprobadas.
--
-- ADR-039 seccion 4. Tres piezas, cada una con su guarda en la base:
--
-- 1. Candidatos con senales deterministas nuevas: diferencia de monto dentro de
--    una tolerancia explicita (absoluta y/o porcentual, numeric exacto), NIT o
--    identificador de contraparte coincidente, referencia contenida en la
--    descripcion de la otra partida y referencia de pago Bre-B. Los candidatos
--    exactos existentes siguen siendo validos. La diferencia de monto se guarda
--    y la base la recalcula desde los movimientos: nunca se confia en el cliente.
-- 2. Reglas de conciliacion versionadas e inmutables, con historial de estado
--    append-only (proposed -> active -> paused/retired) y una aprobacion que
--    respeta el perfil operativo: en `simple` el creador puede aprobar
--    (`self_reviewed`); en `estricto` aprueba otra persona.
-- 3. `approved_rule` deja de estar reservado solo para `match_decision` y solo
--    cuando la fila nombra una regla activa, aprobada, de la misma empresa, con
--    la version exacta, decidida por quien aprobo la regla y sobre fuentes
--    `verified` o `accepted_exception`. Toda aplicacion es reversible por una
--    fila append-only de reversion; la exclusividad de V0025 se conserva con una
--    epoca de reserva por movimiento.
--
-- Monto, fecha y referencia siguen generando candidatos, nunca unicidad dura.
-- Ningun LLM crea, aprueba ni aplica reglas. Solo datos sinteticos (DRG-00).

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

-- --------------------------------------------------------------------------- --
-- 0. Utilidades deterministas
-- --------------------------------------------------------------------------- --

-- Texto comparable: minusculas, sin tildes, solo letras y digitos separados por
-- un espacio. La API aplica exactamente la misma transformacion; el patron de
-- una regla se guarda ya normalizado y nunca se ejecuta como expresion regular.
CREATE FUNCTION fincilia.normalise_match_text(value text)
RETURNS text
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
SET search_path = pg_catalog
AS $function$
  SELECT btrim(regexp_replace(
    translate(lower(coalesce(value, '')),
              'áàäâãéèëêíìïîóòöôõúùüûñç',
              'aaaaaeeeeiiiiooooouuuunc'),
    '[^a-z0-9]+', ' ', 'g'))
$function$;

REVOKE ALL ON FUNCTION fincilia.normalise_match_text(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.normalise_match_text(text)
  TO fincilia_app, fincilia_migrator;

CREATE FUNCTION fincilia.text_array_is_distinct(items text[])
RETURNS boolean
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
SET search_path = pg_catalog
AS $function$
  SELECT cardinality(items) = (SELECT count(DISTINCT item) FROM unnest(items) item)
$function$;

REVOKE ALL ON FUNCTION fincilia.text_array_is_distinct(text[]) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.text_array_is_distinct(text[])
  TO fincilia_app, fincilia_migrator;

-- --------------------------------------------------------------------------- --
-- 1. Senales y diferencia de monto en el candidato
-- --------------------------------------------------------------------------- --

ALTER TABLE fincilia.match_candidate
  ADD COLUMN amount_difference numeric(38, 12);
ALTER TABLE fincilia.match_candidate
  ADD COLUMN amount_tolerance_absolute numeric(38, 12);
ALTER TABLE fincilia.match_candidate
  ADD COLUMN amount_tolerance_percent numeric(9, 6);

ALTER TABLE fincilia.match_candidate
  DROP CONSTRAINT ck_match_candidate_signals;

-- Cuatro senales estructurales siempre; exactamente una de monto (exacto o
-- dentro de tolerancia); hasta cuatro senales de afinidad opcionales. Ningun
-- duplicado. Los candidatos exactos de V0017 (5 o 6 senales) siguen validos.
ALTER TABLE fincilia.match_candidate
  ADD CONSTRAINT ck_match_candidate_signals CHECK (
    cardinality(signals) BETWEEN 5 AND 9
    AND fincilia.text_array_is_distinct(signals)
    AND signals <@ ARRAY[
      'exact_amount', 'amount_within_tolerance', 'same_currency',
      'opposite_direction', 'different_financial_account',
      'date_within_explicit_window', 'same_normalised_reference',
      'same_counterparty_id', 'reference_contained', 'payment_reference']::text[]
    AND signals @> ARRAY[
      'same_currency', 'opposite_direction', 'different_financial_account',
      'date_within_explicit_window']::text[]
    AND (('exact_amount' = ANY(signals)) <> ('amount_within_tolerance' = ANY(signals))));

ALTER TABLE fincilia.match_candidate
  ADD CONSTRAINT ck_match_candidate_amount_difference CHECK (
    (('exact_amount' = ANY(signals))
      AND amount_difference IS NULL
      AND amount_tolerance_absolute IS NULL
      AND amount_tolerance_percent IS NULL)
    OR (('amount_within_tolerance' = ANY(signals))
      AND amount_difference > 0
      AND (amount_tolerance_absolute IS NOT NULL OR amount_tolerance_percent IS NOT NULL)
      AND (amount_tolerance_absolute IS NULL
           OR amount_tolerance_absolute BETWEEN 0 AND 10000000)
      AND (amount_tolerance_percent IS NULL
           OR amount_tolerance_percent BETWEEN 0 AND 5)));

-- La diferencia se recalcula desde los movimientos. Un candidato que dice
-- «exacto» con montos distintos, o una diferencia distinta de la real, o fuera
-- de la tolerancia declarada, no entra.
CREATE FUNCTION fincilia.validate_match_candidate_amount()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  left_amount numeric;
  right_amount numeric;
  left_currency text;
  right_currency text;
  difference numeric;
  allowance numeric;
BEGIN
  SELECT amount, currency_code INTO left_amount, left_currency
  FROM fincilia.canonical_movement
  WHERE movement_id = NEW.left_movement_id AND company_id = NEW.company_id;
  SELECT amount, currency_code INTO right_amount, right_currency
  FROM fincilia.canonical_movement
  WHERE movement_id = NEW.right_movement_id AND company_id = NEW.company_id;
  IF left_amount IS NULL OR right_amount IS NULL THEN
    RAISE EXCEPTION 'candidate movement unavailable' USING ERRCODE = '23503';
  END IF;
  IF left_currency <> right_currency THEN
    RAISE EXCEPTION 'candidate amounts are in different currencies'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_match_candidate_amount_evidence';
  END IF;
  difference := abs(left_amount - right_amount);
  IF 'exact_amount' = ANY(NEW.signals) THEN
    IF difference <> 0 THEN
      RAISE EXCEPTION 'an exact candidate needs equal amounts'
        USING ERRCODE = '23514', CONSTRAINT = 'ck_match_candidate_amount_evidence';
    END IF;
  ELSE
    allowance := GREATEST(
      COALESCE(NEW.amount_tolerance_absolute, 0),
      GREATEST(left_amount, right_amount)
        * COALESCE(NEW.amount_tolerance_percent, 0) / 100);
    IF difference = 0
       OR NEW.amount_difference IS DISTINCT FROM difference
       OR difference > allowance THEN
      RAISE EXCEPTION 'the amount difference is not the recorded one or exceeds the tolerance'
        USING ERRCODE = '23514', CONSTRAINT = 'ck_match_candidate_amount_evidence';
    END IF;
  END IF;
  RETURN NEW;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.validate_match_candidate_amount() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.validate_match_candidate_amount()
  TO fincilia_app, fincilia_migrator;

CREATE TRIGGER match_candidate_amount_evidence
  BEFORE INSERT ON fincilia.match_candidate
  FOR EACH ROW EXECUTE FUNCTION fincilia.validate_match_candidate_amount();

-- --------------------------------------------------------------------------- --
-- 2. Reglas de conciliacion
-- --------------------------------------------------------------------------- --

-- Condiciones cerradas: seis claves exactas. El patron es una subcadena ya
-- normalizada; nunca una expresion regular ejecutable.
CREATE FUNCTION fincilia.valid_rule_conditions(conditions jsonb)
RETURNS boolean
LANGUAGE plpgsql
IMMUTABLE
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  pattern text;
BEGIN
  IF conditions IS NULL OR jsonb_typeof(conditions) <> 'object' THEN
    RETURN false;
  END IF;
  IF (SELECT array_agg(key ORDER BY key) FROM jsonb_object_keys(conditions) key)
     IS DISTINCT FROM ARRAY['currency', 'description_contains', 'direction',
                            'financial_account_id', 'max_amount_difference',
                            'schema']::text[] THEN
    RETURN false;
  END IF;
  IF conditions->>'schema' IS DISTINCT FROM 'fnc-rule-v1' THEN
    RETURN false;
  END IF;
  IF jsonb_typeof(conditions->'description_contains') <> 'string' THEN
    RETURN false;
  END IF;
  pattern := conditions->>'description_contains';
  IF length(pattern) NOT BETWEEN 3 AND 120
     OR pattern <> fincilia.normalise_match_text(pattern) THEN
    RETURN false;
  END IF;
  IF jsonb_typeof(conditions->'financial_account_id') NOT IN ('null', 'string')
     OR (jsonb_typeof(conditions->'financial_account_id') = 'string'
         AND (conditions->>'financial_account_id') !~
             '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$') THEN
    RETURN false;
  END IF;
  IF jsonb_typeof(conditions->'direction') NOT IN ('null', 'string')
     OR (jsonb_typeof(conditions->'direction') = 'string'
         AND conditions->>'direction' NOT IN ('inflow', 'outflow')) THEN
    RETURN false;
  END IF;
  IF jsonb_typeof(conditions->'max_amount_difference') <> 'string'
     OR (conditions->>'max_amount_difference') !~ '^[0-9]{1,15}(\.[0-9]{1,12})?$'
     OR (conditions->>'max_amount_difference')::numeric > 10000000 THEN
    RETURN false;
  END IF;
  IF jsonb_typeof(conditions->'currency') <> 'string'
     OR (conditions->>'currency') !~ '^[A-Z]{3}$' THEN
    RETURN false;
  END IF;
  RETURN true;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.valid_rule_conditions(jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.valid_rule_conditions(jsonb)
  TO fincilia_app, fincilia_migrator;

CREATE TABLE fincilia.reconciliation_rule (
  rule_id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id               uuid NOT NULL REFERENCES fincilia.company(company_id),
  version                  integer NOT NULL CHECK (version BETWEEN 1 AND 10000),
  supersedes_rule_id       uuid,
  conditions               jsonb NOT NULL,
  conditions_digest        char(64) NOT NULL CHECK (conditions_digest ~ '^[0-9a-f]{64}$'),
  created_by               uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  created_from_decision_id uuid,
  created_at               timestamptz NOT NULL DEFAULT now(),
  audit_event_id           uuid NOT NULL,

  CONSTRAINT uq_reconciliation_rule_company UNIQUE (rule_id, company_id),
  CONSTRAINT fk_reconciliation_rule_supersedes FOREIGN KEY (supersedes_rule_id, company_id)
    REFERENCES fincilia.reconciliation_rule (rule_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_reconciliation_rule_decision FOREIGN KEY (created_from_decision_id, company_id)
    REFERENCES fincilia.match_decision (decision_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_reconciliation_rule_audit FOREIGN KEY (audit_event_id, company_id)
    REFERENCES fincilia.audit_event (audit_event_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT ck_reconciliation_rule_conditions CHECK (
    fincilia.valid_rule_conditions(conditions)
    AND pg_column_size(conditions) <= 2048),
  CONSTRAINT ck_reconciliation_rule_lineage CHECK (
    (supersedes_rule_id IS NULL) = (version = 1))
);

CREATE INDEX idx_reconciliation_rule_company_time
  ON fincilia.reconciliation_rule (company_id, created_at DESC, rule_id);

CREATE TABLE fincilia.reconciliation_rule_transition (
  transition_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id      uuid NOT NULL REFERENCES fincilia.company(company_id),
  rule_id         uuid NOT NULL,
  sequence        integer NOT NULL CHECK (sequence >= 1),
  from_status     text CHECK (from_status IN ('proposed', 'active', 'paused', 'retired')),
  to_status       text NOT NULL CHECK (to_status IN ('proposed', 'active', 'paused', 'retired')),
  reason_code     text NOT NULL CHECK (reason_code IN (
                    'created', 'approved', 'paused_by_person', 'resumed_by_person',
                    'retired_by_person')),
  actor_id        uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  created_at      timestamptz NOT NULL DEFAULT now(),
  audit_event_id  uuid NOT NULL,

  CONSTRAINT uq_rule_transition_sequence UNIQUE (rule_id, sequence),
  CONSTRAINT fk_rule_transition_rule FOREIGN KEY (rule_id, company_id)
    REFERENCES fincilia.reconciliation_rule (rule_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_rule_transition_audit FOREIGN KEY (audit_event_id, company_id)
    REFERENCES fincilia.audit_event (audit_event_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT ck_rule_transition_origin CHECK (
    (sequence = 1) = (from_status IS NULL))
);

CREATE TABLE fincilia.reconciliation_rule_approval (
  approval_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id      uuid NOT NULL REFERENCES fincilia.company(company_id),
  rule_id         uuid NOT NULL,
  approved_by     uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  review_mode     text NOT NULL DEFAULT 'independent'
                    CHECK (review_mode IN ('independent', 'self_reviewed')),
  approved_at     timestamptz NOT NULL DEFAULT now(),
  audit_event_id  uuid NOT NULL,

  CONSTRAINT uq_rule_approval_rule UNIQUE (rule_id),
  CONSTRAINT uq_rule_approval_company UNIQUE (approval_id, company_id),
  CONSTRAINT fk_rule_approval_rule FOREIGN KEY (rule_id, company_id)
    REFERENCES fincilia.reconciliation_rule (rule_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_rule_approval_audit FOREIGN KEY (audit_event_id, company_id)
    REFERENCES fincilia.audit_event (audit_event_id, company_id) ON DELETE RESTRICT
);

CREATE TABLE fincilia.reconciliation_rule_receipt (
  receipt_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id      uuid NOT NULL REFERENCES fincilia.company(company_id),
  actor_id        uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  action          text NOT NULL CHECK (action IN (
                    'create', 'approve', 'pause', 'resume', 'retire', 'apply',
                    'revert')),
  idempotency_key text NOT NULL CHECK (
                    length(idempotency_key) BETWEEN 16 AND 128
                    AND idempotency_key ~ '^[A-Za-z0-9._:-]+$'),
  request_digest  char(64) NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
  result          jsonb NOT NULL CHECK (
                    jsonb_typeof(result) = 'object' AND pg_column_size(result) <= 65536),
  created_at      timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_rule_receipt_key UNIQUE (company_id, actor_id, idempotency_key)
);

-- Estado vigente: la ultima transicion. Sin transiciones, la regla no existe.
CREATE FUNCTION fincilia.reconciliation_rule_status(requested_rule_id uuid)
RETURNS text
LANGUAGE sql
STABLE
SET search_path = pg_catalog, fincilia
AS $function$
  SELECT t.to_status FROM fincilia.reconciliation_rule_transition t
  WHERE t.rule_id = requested_rule_id
  ORDER BY t.sequence DESC LIMIT 1
$function$;

REVOKE ALL ON FUNCTION fincilia.reconciliation_rule_status(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.reconciliation_rule_status(uuid)
  TO fincilia_app, fincilia_migrator;

CREATE FUNCTION fincilia.validate_reconciliation_rule()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  source_decision fincilia.match_decision%ROWTYPE;
  previous_version integer;
BEGIN
  IF NEW.created_from_decision_id IS NOT NULL THEN
    SELECT * INTO source_decision FROM fincilia.match_decision
    WHERE decision_id = NEW.created_from_decision_id AND company_id = NEW.company_id;
    -- Una regla nace de una decision humana confirmada, nunca de otra regla.
    IF source_decision.decision_id IS NULL
       OR source_decision.decision <> 'confirmed'
       OR source_decision.review_mode = 'approved_rule' THEN
      RAISE EXCEPTION 'a rule is created from a confirmed human decision'
        USING ERRCODE = '23514', CONSTRAINT = 'ck_reconciliation_rule_source';
    END IF;
  END IF;
  IF jsonb_typeof(NEW.conditions->'financial_account_id') = 'string'
     AND NOT EXISTS (
       SELECT 1 FROM fincilia.financial_account a
       WHERE a.account_id = (NEW.conditions->>'financial_account_id')::uuid
         AND a.company_id = NEW.company_id) THEN
    RAISE EXCEPTION 'rule account is unavailable in this company'
      USING ERRCODE = '23503', CONSTRAINT = 'ck_reconciliation_rule_account';
  END IF;
  IF NEW.supersedes_rule_id IS NOT NULL THEN
    SELECT version INTO previous_version FROM fincilia.reconciliation_rule
    WHERE rule_id = NEW.supersedes_rule_id AND company_id = NEW.company_id;
    IF previous_version IS NULL OR NEW.version <> previous_version + 1 THEN
      RAISE EXCEPTION 'rule version must follow the superseded rule'
        USING ERRCODE = '23514', CONSTRAINT = 'ck_reconciliation_rule_lineage';
    END IF;
  END IF;
  NEW.created_at := now();
  RETURN NEW;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.validate_reconciliation_rule() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.validate_reconciliation_rule()
  TO fincilia_app, fincilia_migrator;

CREATE TRIGGER reconciliation_rule_validate
  BEFORE INSERT ON fincilia.reconciliation_rule
  FOR EACH ROW EXECUTE FUNCTION fincilia.validate_reconciliation_rule();

-- Toda regla nace `proposed` con su primera transicion, en la misma sentencia.
CREATE FUNCTION fincilia.start_reconciliation_rule()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
BEGIN
  INSERT INTO fincilia.reconciliation_rule_transition
    (company_id, rule_id, sequence, from_status, to_status, reason_code,
     actor_id, audit_event_id)
  VALUES (NEW.company_id, NEW.rule_id, 1, NULL, 'proposed', 'created',
          NEW.created_by, NEW.audit_event_id);
  RETURN NULL;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.start_reconciliation_rule() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.start_reconciliation_rule()
  TO fincilia_app, fincilia_migrator;

CREATE TRIGGER reconciliation_rule_start
  AFTER INSERT ON fincilia.reconciliation_rule
  FOR EACH ROW EXECUTE FUNCTION fincilia.start_reconciliation_rule();

CREATE FUNCTION fincilia.validate_reconciliation_rule_transition()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  current_status text;
  next_sequence integer;
  rule_author uuid;
  approver uuid;
BEGIN
  PERFORM pg_advisory_xact_lock(hashtextextended(NEW.rule_id::text, 39003));
  SELECT created_by INTO rule_author FROM fincilia.reconciliation_rule
  WHERE rule_id = NEW.rule_id AND company_id = NEW.company_id;
  IF rule_author IS NULL THEN
    RAISE EXCEPTION 'rule unavailable' USING ERRCODE = '23503';
  END IF;
  SELECT t.to_status INTO current_status FROM fincilia.reconciliation_rule_transition t
  WHERE t.rule_id = NEW.rule_id ORDER BY t.sequence DESC LIMIT 1;
  SELECT COALESCE(max(t.sequence), 0) + 1 INTO next_sequence
  FROM fincilia.reconciliation_rule_transition t WHERE t.rule_id = NEW.rule_id;
  IF NEW.sequence <> next_sequence THEN
    RAISE EXCEPTION 'rule transition sequence is not next'
      USING ERRCODE = '40001', CONSTRAINT = 'ck_rule_transition_sequence';
  END IF;
  SELECT approved_by INTO approver FROM fincilia.reconciliation_rule_approval
  WHERE rule_id = NEW.rule_id AND company_id = NEW.company_id;

  IF current_status IS NULL THEN
    IF NEW.from_status IS NOT NULL OR NEW.to_status <> 'proposed'
       OR NEW.reason_code <> 'created' OR NEW.actor_id <> rule_author THEN
      RAISE EXCEPTION 'a rule starts proposed by its author'
        USING ERRCODE = '23514', CONSTRAINT = 'ck_rule_transition_graph';
    END IF;
  ELSIF NEW.from_status IS DISTINCT FROM current_status
     OR NOT (
       (current_status = 'proposed' AND NEW.to_status = 'active'
         AND NEW.reason_code = 'approved' AND approver IS NOT NULL
         AND NEW.actor_id = approver)
       OR (current_status = 'active' AND NEW.to_status = 'paused'
           AND NEW.reason_code = 'paused_by_person')
       OR (current_status = 'paused' AND NEW.to_status = 'active'
           AND NEW.reason_code = 'resumed_by_person' AND approver IS NOT NULL)
       OR (current_status IN ('proposed', 'active', 'paused')
           AND NEW.to_status = 'retired' AND NEW.reason_code = 'retired_by_person')) THEN
    RAISE EXCEPTION 'rule transition is not allowed from the current status'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_rule_transition_graph';
  END IF;
  NEW.created_at := now();
  RETURN NEW;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.validate_reconciliation_rule_transition() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.validate_reconciliation_rule_transition()
  TO fincilia_app, fincilia_migrator;

CREATE TRIGGER reconciliation_rule_transition_validate
  BEFORE INSERT ON fincilia.reconciliation_rule_transition
  FOR EACH ROW EXECUTE FUNCTION fincilia.validate_reconciliation_rule_transition();

-- La aprobacion respeta el perfil: `estricto` exige otra persona y `simple`
-- acepta al autor marcandolo `self_reviewed`. El cliente no elige el modo.
CREATE FUNCTION fincilia.validate_reconciliation_rule_approval()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  rule_author uuid;
  mode text;
BEGIN
  PERFORM pg_advisory_xact_lock(hashtextextended(NEW.rule_id::text, 39003));
  SELECT created_by INTO rule_author FROM fincilia.reconciliation_rule
  WHERE rule_id = NEW.rule_id AND company_id = NEW.company_id;
  IF rule_author IS NULL THEN
    RAISE EXCEPTION 'rule unavailable' USING ERRCODE = '23503';
  END IF;
  IF fincilia.reconciliation_rule_status(NEW.rule_id) IS DISTINCT FROM 'proposed' THEN
    RAISE EXCEPTION 'only a proposed rule can be approved'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_rule_approval_proposed';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM fincilia.subject s
                 WHERE s.subject_id = NEW.approved_by AND s.status = 'active'
                   AND s.subject_kind = 'person') THEN
    RAISE EXCEPTION 'rule approver must be an active person'
      USING ERRCODE = '42501', CONSTRAINT = 'ck_rule_approval_sod';
  END IF;
  mode := fincilia.review_mode_for(NEW.company_id, rule_author, NEW.approved_by);
  IF mode IS NULL THEN
    RAISE EXCEPTION 'segregation of duties: the rule author cannot approve it'
      USING ERRCODE = '42501', CONSTRAINT = 'ck_rule_approval_sod';
  END IF;
  NEW.review_mode := mode;
  NEW.approved_at := now();
  RETURN NEW;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.validate_reconciliation_rule_approval() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.validate_reconciliation_rule_approval()
  TO fincilia_app, fincilia_migrator;

CREATE TRIGGER reconciliation_rule_approval_validate
  BEFORE INSERT ON fincilia.reconciliation_rule_approval
  FOR EACH ROW EXECUTE FUNCTION fincilia.validate_reconciliation_rule_approval();

CREATE FUNCTION fincilia.activate_approved_reconciliation_rule()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  next_sequence integer;
BEGIN
  SELECT COALESCE(max(t.sequence), 0) + 1 INTO next_sequence
  FROM fincilia.reconciliation_rule_transition t WHERE t.rule_id = NEW.rule_id;
  INSERT INTO fincilia.reconciliation_rule_transition
    (company_id, rule_id, sequence, from_status, to_status, reason_code,
     actor_id, audit_event_id)
  VALUES (NEW.company_id, NEW.rule_id, next_sequence, 'proposed', 'active',
          'approved', NEW.approved_by, NEW.audit_event_id);
  RETURN NULL;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.activate_approved_reconciliation_rule() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.activate_approved_reconciliation_rule()
  TO fincilia_app, fincilia_migrator;

CREATE TRIGGER reconciliation_rule_approval_activate
  AFTER INSERT ON fincilia.reconciliation_rule_approval
  FOR EACH ROW EXECUTE FUNCTION fincilia.activate_approved_reconciliation_rule();

-- --------------------------------------------------------------------------- --
-- 3. `approved_rule` en la decision de cruce
-- --------------------------------------------------------------------------- --

ALTER TABLE fincilia.match_decision
  ADD COLUMN rule_id uuid;
ALTER TABLE fincilia.match_decision
  ADD COLUMN rule_version integer;

ALTER TABLE fincilia.match_decision
  ADD CONSTRAINT fk_match_decision_rule FOREIGN KEY (rule_id, company_id)
    REFERENCES fincilia.reconciliation_rule (rule_id, company_id) ON DELETE RESTRICT;

ALTER TABLE fincilia.match_decision
  DROP CONSTRAINT match_decision_reason_code_check;
ALTER TABLE fincilia.match_decision
  ADD CONSTRAINT ck_match_decision_reason CHECK (reason_code IN (
    'documented_counterpart', 'documented_transfer', 'reference_supported',
    'different_event', 'timing_mismatch', 'wrong_counterpart',
    'insufficient_evidence', 'approved_rule_match'));

-- Una fila `approved_rule` siempre nombra regla y version, confirma y usa su
-- motivo propio. Ninguna otra fila puede usar ese motivo ni nombrar una regla.
ALTER TABLE fincilia.match_decision
  ADD CONSTRAINT ck_match_decision_rule CHECK (
    (rule_id IS NULL) = (rule_version IS NULL)
    AND ((review_mode = 'approved_rule') = (rule_id IS NOT NULL))
    AND ((reason_code = 'approved_rule_match') = (rule_id IS NOT NULL))
    AND (rule_id IS NULL OR decision = 'confirmed'));

CREATE INDEX idx_match_decision_rule
  ON fincilia.match_decision (company_id, rule_id) WHERE rule_id IS NOT NULL;

CREATE OR REPLACE FUNCTION fincilia.enforce_match_decision_sod()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  author_id uuid;
  expected_left uuid;
  expected_right uuid;
  recorded_difference numeric;
  mode text;
  rule_row fincilia.reconciliation_rule%ROWTYPE;
  rule_approver uuid;
  pattern text;
  account_ref uuid;
  direction_ref text;
BEGIN
  SELECT proposed_by, left_movement_id, right_movement_id, amount_difference
    INTO author_id, expected_left, expected_right, recorded_difference
  FROM fincilia.match_candidate
  WHERE candidate_id = NEW.candidate_id AND company_id = NEW.company_id;

  IF author_id IS NULL THEN
    RAISE EXCEPTION 'candidate unavailable' USING ERRCODE = '23503';
  END IF;

  IF NEW.review_mode = 'approved_rule' OR NEW.rule_id IS NOT NULL THEN
    IF NEW.rule_id IS NULL OR NEW.review_mode <> 'approved_rule' THEN
      RAISE EXCEPTION 'approved_rule review mode is reserved for approved rules'
        USING ERRCODE = '23514', CONSTRAINT = 'ck_review_mode_reserved';
    END IF;
    SELECT * INTO rule_row FROM fincilia.reconciliation_rule
    WHERE rule_id = NEW.rule_id AND company_id = NEW.company_id;
    SELECT approved_by INTO rule_approver FROM fincilia.reconciliation_rule_approval
    WHERE rule_id = NEW.rule_id AND company_id = NEW.company_id;
    IF rule_row.rule_id IS NULL
       OR rule_row.version IS DISTINCT FROM NEW.rule_version
       OR rule_approver IS NULL
       OR fincilia.reconciliation_rule_status(NEW.rule_id) IS DISTINCT FROM 'active'
       OR NEW.decided_by <> rule_approver
       OR NEW.decision <> 'confirmed' THEN
      RAISE EXCEPTION 'approved_rule review mode is reserved for approved rules'
        USING ERRCODE = '23514', CONSTRAINT = 'ck_review_mode_reserved';
    END IF;

    pattern := rule_row.conditions->>'description_contains';
    account_ref := NULLIF(rule_row.conditions->>'financial_account_id', '')::uuid;
    direction_ref := NULLIF(rule_row.conditions->>'direction', '');
    -- La regla solo confirma lo que cumple todas sus condiciones y solo sobre
    -- fuentes verificadas o con excepcion aceptada. Partial, unknown o
    -- unverified nunca alimentan esta via.
    IF NOT EXISTS (
      SELECT 1
      FROM fincilia.canonical_movement l
      JOIN fincilia.dataset_version dl
        ON dl.dataset_version_id = l.dataset_version_id AND dl.company_id = l.company_id
      JOIN fincilia.canonical_movement r
        ON r.movement_id = expected_right AND r.company_id = l.company_id
      JOIN fincilia.dataset_version dr
        ON dr.dataset_version_id = r.dataset_version_id AND dr.company_id = r.company_id
      WHERE l.movement_id = expected_left
        AND l.company_id = NEW.company_id
        AND dl.state IN ('validated', 'published')
        AND dr.state IN ('validated', 'published')
        AND dl.completeness_state IN ('verified', 'accepted_exception')
        AND dr.completeness_state IN ('verified', 'accepted_exception')
        AND dl.lineage_state = 'complete' AND dr.lineage_state = 'complete'
        AND l.lineage_state = 'complete' AND r.lineage_state = 'complete'
        AND l.state IN ('proposed', 'confirmed') AND r.state IN ('proposed', 'confirmed')
        AND l.currency_code = rule_row.conditions->>'currency'
        AND r.currency_code = rule_row.conditions->>'currency'
        AND COALESCE(recorded_difference, 0)
            <= (rule_row.conditions->>'max_amount_difference')::numeric
        AND (
          (strpos(fincilia.normalise_match_text(l.description), pattern) > 0
            AND (account_ref IS NULL OR l.financial_account_id = account_ref)
            AND (direction_ref IS NULL OR l.direction = direction_ref))
          OR (strpos(fincilia.normalise_match_text(r.description), pattern) > 0
            AND (account_ref IS NULL OR r.financial_account_id = account_ref)
            AND (direction_ref IS NULL OR r.direction = direction_ref)))
    ) THEN
      RAISE EXCEPTION 'the candidate does not satisfy the approved rule'
        USING ERRCODE = '23514', CONSTRAINT = 'ck_match_decision_rule_eligible';
    END IF;
  ELSE
    mode := fincilia.review_mode_for(NEW.company_id, author_id, NEW.decided_by);
    IF NEW.decision = 'confirmed' AND mode IS NULL THEN
      RAISE EXCEPTION 'segregation of duties: proposer cannot confirm'
        USING ERRCODE = '42501';
    END IF;
    NEW.review_mode := COALESCE(mode, 'self_reviewed');
  END IF;

  IF NEW.evidence_refs <> jsonb_build_array(
       jsonb_build_object('kind', 'movement', 'ref', expected_left::text),
       jsonb_build_object('kind', 'movement', 'ref', expected_right::text)) THEN
    RAISE EXCEPTION 'decision evidence must name the ordered candidate pair'
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END
$function$;

-- --------------------------------------------------------------------------- --
-- 4. Reversion append-only y exclusividad por epoca
-- --------------------------------------------------------------------------- --

CREATE TABLE fincilia.match_decision_reversal (
  reversal_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id      uuid NOT NULL REFERENCES fincilia.company(company_id),
  decision_id     uuid NOT NULL,
  candidate_id    uuid NOT NULL,
  reason_code     text NOT NULL CHECK (reason_code IN (
                    'different_event', 'timing_mismatch', 'wrong_counterpart',
                    'insufficient_evidence', 'rule_too_broad')),
  reversed_by     uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  reversed_at     timestamptz NOT NULL DEFAULT now(),
  audit_event_id  uuid NOT NULL,

  CONSTRAINT uq_match_reversal_company UNIQUE (reversal_id, company_id),
  CONSTRAINT uq_match_reversal_decision UNIQUE (decision_id),
  CONSTRAINT fk_match_reversal_decision FOREIGN KEY (decision_id, company_id)
    REFERENCES fincilia.match_decision (decision_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_match_reversal_candidate FOREIGN KEY (candidate_id, company_id)
    REFERENCES fincilia.match_candidate (candidate_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_match_reversal_audit FOREIGN KEY (audit_event_id, company_id)
    REFERENCES fincilia.audit_event (audit_event_id, company_id) ON DELETE RESTRICT
);

CREATE INDEX idx_match_reversal_company_time
  ON fincilia.match_decision_reversal (company_id, reversed_at DESC, reversal_id);

-- Hoy se revierten aplicaciones de regla, que es lo que ADR-039 exige. Una
-- decision humana sigue siendo terminal como en V0017.
CREATE FUNCTION fincilia.validate_match_decision_reversal()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  target fincilia.match_decision%ROWTYPE;
  range_start date;
  range_end date;
BEGIN
  PERFORM pg_advisory_xact_lock(hashtextextended(NEW.company_id::text, 35006));
  SELECT * INTO target FROM fincilia.match_decision
  WHERE decision_id = NEW.decision_id AND company_id = NEW.company_id;
  IF target.decision_id IS NULL OR target.candidate_id <> NEW.candidate_id THEN
    RAISE EXCEPTION 'decision unavailable' USING ERRCODE = '23503';
  END IF;
  IF target.decision <> 'confirmed' OR target.review_mode <> 'approved_rule' THEN
    RAISE EXCEPTION 'only a rule application can be reverted'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_match_reversal_rule_only';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM fincilia.subject s
                 WHERE s.subject_id = NEW.reversed_by AND s.status = 'active'
                   AND s.subject_kind = 'person') THEN
    RAISE EXCEPTION 'a reversal is decided by an active person'
      USING ERRCODE = '42501', CONSTRAINT = 'ck_match_reversal_person';
  END IF;
  SELECT LEAST(l.occurred_on, r.occurred_on), GREATEST(l.occurred_on, r.occurred_on)
    INTO range_start, range_end
  FROM fincilia.match_candidate c
  JOIN fincilia.canonical_movement l
    ON l.movement_id = c.left_movement_id AND l.company_id = c.company_id
  JOIN fincilia.canonical_movement r
    ON r.movement_id = c.right_movement_id AND r.company_id = c.company_id
  WHERE c.candidate_id = NEW.candidate_id AND c.company_id = NEW.company_id;
  IF range_start IS NULL OR fincilia.accounting_period_is_closed(
      NEW.company_id, range_start, range_end) THEN
    RAISE EXCEPTION 'financial write intersects a closed accounting period'
      USING ERRCODE = '55000', CONSTRAINT = 'ck_financial_write_period_open';
  END IF;
  NEW.reversed_at := now();
  RETURN NEW;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.validate_match_decision_reversal() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.validate_match_decision_reversal()
  TO fincilia_app, fincilia_migrator;

CREATE TRIGGER match_decision_reversal_validate
  BEFORE INSERT ON fincilia.match_decision_reversal
  FOR EACH ROW EXECUTE FUNCTION fincilia.validate_match_decision_reversal();

-- V0025 reservaba un movimiento para siempre con la PK (empresa, movimiento).
-- Con reversiones, la reserva vigente es la de la epoca actual: tantas como
-- reversiones haya tenido ese movimiento. Dos confirmaciones concurrentes
-- calculan la misma epoca y la PK, con el mismo nombre de siempre, deja una.
-- Las filas existentes quedan en la epoca 0, que es exactamente su estado.
ALTER TABLE fincilia.match_confirmation_member
  ADD COLUMN reservation_epoch integer NOT NULL DEFAULT 0
    CONSTRAINT ck_match_confirmation_epoch CHECK (reservation_epoch >= 0);
ALTER TABLE fincilia.match_confirmation_member
  DROP CONSTRAINT pk_match_confirmation_member;
ALTER TABLE fincilia.match_confirmation_member
  ADD CONSTRAINT pk_match_confirmation_member
    PRIMARY KEY (company_id, movement_id, reservation_epoch);

GRANT SELECT ON fincilia.match_decision_reversal TO fincilia_dispatch;
GRANT CREATE ON SCHEMA fincilia TO fincilia_dispatch;
SET LOCAL ROLE fincilia_dispatch;

CREATE OR REPLACE FUNCTION fincilia.reserve_confirmed_match_members()
RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $function$
DECLARE
  expected_left uuid;
  expected_right uuid;
BEGIN
  IF NEW.decision <> 'confirmed' THEN
    RETURN NEW;
  END IF;

  SELECT left_movement_id, right_movement_id
    INTO expected_left, expected_right
  FROM fincilia.match_candidate
  WHERE candidate_id = NEW.candidate_id AND company_id = NEW.company_id;

  IF expected_left IS NULL OR expected_right IS NULL THEN
    RAISE EXCEPTION 'candidate unavailable for confirmation reservation'
      USING ERRCODE = '23503';
  END IF;

  INSERT INTO fincilia.match_confirmation_member
    (company_id, movement_id, candidate_id, decision_id, member_side,
     confirmed_at, reservation_epoch)
  SELECT NEW.company_id, side.movement_id, NEW.candidate_id, NEW.decision_id,
         side.member_side, NEW.decided_at,
         (SELECT count(*)::integer
            FROM fincilia.match_confirmation_member prior
            JOIN fincilia.match_decision_reversal reversal
              ON reversal.decision_id = prior.decision_id
             AND reversal.company_id = prior.company_id
           WHERE prior.company_id = NEW.company_id
             AND prior.movement_id = side.movement_id)
  FROM (VALUES (expected_left, 'left'), (expected_right, 'right'))
    AS side(movement_id, member_side);

  RETURN NEW;
END
$function$;

REVOKE ALL PRIVILEGES ON FUNCTION fincilia.reserve_confirmed_match_members() FROM PUBLIC;

RESET ROLE;
REVOKE CREATE ON SCHEMA fincilia FROM fincilia_dispatch;

-- --------------------------------------------------------------------------- --
-- 5. Append-only, RLS y privilegios
-- --------------------------------------------------------------------------- --

CREATE TRIGGER reconciliation_rule_append_only
  BEFORE UPDATE OR DELETE ON fincilia.reconciliation_rule
  FOR EACH ROW EXECUTE FUNCTION fincilia.reject_match_ledger_mutation();
CREATE TRIGGER reconciliation_rule_transition_append_only
  BEFORE UPDATE OR DELETE ON fincilia.reconciliation_rule_transition
  FOR EACH ROW EXECUTE FUNCTION fincilia.reject_match_ledger_mutation();
CREATE TRIGGER reconciliation_rule_approval_append_only
  BEFORE UPDATE OR DELETE ON fincilia.reconciliation_rule_approval
  FOR EACH ROW EXECUTE FUNCTION fincilia.reject_match_ledger_mutation();
CREATE TRIGGER reconciliation_rule_receipt_append_only
  BEFORE UPDATE OR DELETE ON fincilia.reconciliation_rule_receipt
  FOR EACH ROW EXECUTE FUNCTION fincilia.reject_match_ledger_mutation();
CREATE TRIGGER match_decision_reversal_append_only
  BEFORE UPDATE OR DELETE ON fincilia.match_decision_reversal
  FOR EACH ROW EXECUTE FUNCTION fincilia.reject_match_ledger_mutation();

ALTER TABLE fincilia.reconciliation_rule ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.reconciliation_rule FORCE ROW LEVEL SECURITY;
CREATE POLICY reconciliation_rule_isolation ON fincilia.reconciliation_rule
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.reconciliation_rule_transition ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.reconciliation_rule_transition FORCE ROW LEVEL SECURITY;
CREATE POLICY reconciliation_rule_transition_isolation
  ON fincilia.reconciliation_rule_transition
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.reconciliation_rule_approval ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.reconciliation_rule_approval FORCE ROW LEVEL SECURITY;
CREATE POLICY reconciliation_rule_approval_isolation
  ON fincilia.reconciliation_rule_approval
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.reconciliation_rule_receipt ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.reconciliation_rule_receipt FORCE ROW LEVEL SECURITY;
CREATE POLICY reconciliation_rule_receipt_isolation
  ON fincilia.reconciliation_rule_receipt
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.match_decision_reversal ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.match_decision_reversal FORCE ROW LEVEL SECURITY;
CREATE POLICY match_decision_reversal_isolation ON fincilia.match_decision_reversal
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

REVOKE ALL ON fincilia.reconciliation_rule, fincilia.reconciliation_rule_transition,
  fincilia.reconciliation_rule_approval, fincilia.reconciliation_rule_receipt,
  fincilia.match_decision_reversal FROM PUBLIC;
GRANT SELECT, INSERT ON fincilia.reconciliation_rule,
  fincilia.reconciliation_rule_transition, fincilia.reconciliation_rule_approval,
  fincilia.reconciliation_rule_receipt, fincilia.match_decision_reversal
  TO fincilia_app;
REVOKE UPDATE, DELETE ON fincilia.reconciliation_rule,
  fincilia.reconciliation_rule_transition, fincilia.reconciliation_rule_approval,
  fincilia.reconciliation_rule_receipt, fincilia.match_decision_reversal
  FROM fincilia_app;
REVOKE ALL ON fincilia.reconciliation_rule, fincilia.reconciliation_rule_transition,
  fincilia.reconciliation_rule_approval, fincilia.reconciliation_rule_receipt,
  fincilia.match_decision_reversal FROM fincilia_worker;

COMMENT ON TABLE fincilia.reconciliation_rule IS
  'Regla de conciliacion determinista e inmutable (ADR-039 §4). El estado vive en '
  'reconciliation_rule_transition; pausar o retirar nunca borra decisiones.';
COMMENT ON TABLE fincilia.match_decision_reversal IS
  'Reversion append-only de una aplicacion de regla. Libera la reserva del '
  'movimiento abriendo una nueva epoca en match_confirmation_member.';

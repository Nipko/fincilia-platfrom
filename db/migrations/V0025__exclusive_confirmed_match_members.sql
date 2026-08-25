-- V0025: una confirmacion humana no puede reservar el mismo movimiento dos veces.
--
-- La tabla es una guarda de integridad del ledger de V0017. No suma importes,
-- no cambia movimientos y no demuestra conciliacion de saldos. Las propuestas
-- superpuestas y los rechazos siguen permitidos; solo `confirmed` materializa
-- exactamente dos miembros.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

CREATE TABLE fincilia.match_confirmation_member (
  company_id   uuid NOT NULL REFERENCES fincilia.company(company_id),
  movement_id  uuid NOT NULL,
  candidate_id uuid NOT NULL,
  decision_id  uuid NOT NULL,
  member_side  text NOT NULL CHECK (member_side IN ('left', 'right')),
  confirmed_at timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT pk_match_confirmation_member PRIMARY KEY (company_id, movement_id),
  CONSTRAINT uq_match_confirmation_decision_side UNIQUE (decision_id, member_side),
  CONSTRAINT fk_match_confirmation_candidate FOREIGN KEY (candidate_id, company_id)
    REFERENCES fincilia.match_candidate(candidate_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_match_confirmation_decision FOREIGN KEY (decision_id, company_id)
    REFERENCES fincilia.match_decision(decision_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_match_confirmation_movement FOREIGN KEY (movement_id, company_id)
    REFERENCES fincilia.canonical_movement(movement_id, company_id) ON DELETE RESTRICT
);

CREATE INDEX idx_match_confirmation_candidate
  ON fincilia.match_confirmation_member(company_id, candidate_id);

ALTER TABLE fincilia.match_confirmation_member ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.match_confirmation_member FORCE ROW LEVEL SECURITY;
CREATE POLICY match_confirmation_member_isolation
  ON fincilia.match_confirmation_member
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

REVOKE ALL ON fincilia.match_confirmation_member FROM PUBLIC;
GRANT SELECT ON fincilia.match_confirmation_member TO fincilia_app;
GRANT SELECT, INSERT ON fincilia.match_confirmation_member TO fincilia_dispatch;
GRANT SELECT ON fincilia.match_candidate TO fincilia_dispatch;

GRANT CREATE ON SCHEMA fincilia TO fincilia_dispatch;

CREATE FUNCTION fincilia.reserve_confirmed_match_members()
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
    (company_id, movement_id, candidate_id, decision_id, member_side, confirmed_at)
  VALUES
    (NEW.company_id, expected_left, NEW.candidate_id, NEW.decision_id,
     'left', NEW.decided_at),
    (NEW.company_id, expected_right, NEW.candidate_id, NEW.decision_id,
     'right', NEW.decided_at);

  RETURN NEW;
END
$function$;

REVOKE ALL ON FUNCTION fincilia.reserve_confirmed_match_members() FROM PUBLIC;

CREATE TRIGGER match_decision_reserve_members
  AFTER INSERT ON fincilia.match_decision
  FOR EACH ROW EXECUTE FUNCTION fincilia.reserve_confirmed_match_members();

ALTER FUNCTION fincilia.reserve_confirmed_match_members() OWNER TO fincilia_dispatch;
REVOKE CREATE ON SCHEMA fincilia FROM fincilia_dispatch;

CREATE TRIGGER match_confirmation_member_append_only
  BEFORE UPDATE OR DELETE ON fincilia.match_confirmation_member
  FOR EACH ROW EXECUTE FUNCTION fincilia.reject_match_ledger_mutation();

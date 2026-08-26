-- FNC-CLS-002 — observaciones canonicas de saldo por cuenta.
--
-- Una observacion de saldo es un hecho financiero inmutable respaldado por una
-- celda de una fila publicada. No es una evaluacion de completitud, no cuadra
-- una conciliacion y no habilita un cierre. Hasta que una rebanada posterior
-- materialice el camino completo del campo, nace `required_pending`.

-- Permite que la moneda de la observacion forme parte de la FK. Sin esto la API
-- podria comprobarla y una escritura directa con el rol runtime no.
ALTER TABLE fincilia.financial_account
  ADD CONSTRAINT uq_account_currency_identity
  UNIQUE (account_id, company_id, currency_code);

CREATE TABLE fincilia.account_balance (
  balance_id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id               uuid NOT NULL REFERENCES fincilia.company(company_id),
  financial_account_id     uuid NOT NULL,
  source_record_id         uuid NOT NULL,
  balance_type             text NOT NULL CHECK (balance_type IN (
                             'opening', 'closing', 'running', 'available', 'ledger')),
  amount                   numeric(38, 12) NOT NULL,
  currency_code            text NOT NULL CHECK (currency_code ~ '^[A-Z]{3}$'),
  as_of                    timestamptz NOT NULL,
  source_timezone          text NOT NULL CHECK (length(source_timezone) BETWEEN 3 AND 64),
  amount_field_index       integer NOT NULL CHECK (amount_field_index >= 0),
  as_of_field_index        integer NOT NULL CHECK (as_of_field_index >= 0),
  field_digests            jsonb NOT NULL,
  observation_key          char(64) NOT NULL
                              CHECK (observation_key ~ '^[0-9a-f]{64}$'),
  prepared_by              uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  engine_release_id        uuid NOT NULL REFERENCES fincilia.engine_release(release_id),
  canonical_schema_version text NOT NULL CHECK (length(canonical_schema_version) BETWEEN 1 AND 32),
  lineage_state            text NOT NULL DEFAULT 'required_pending'
                              CHECK (lineage_state IN (
                                'required_pending', 'complete', 'invalidated')),
  created_at               timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_account_balance_identity UNIQUE (balance_id, company_id),
  CONSTRAINT uq_account_balance_observation UNIQUE (
    company_id, source_record_id, financial_account_id, balance_type,
    as_of, amount_field_index, as_of_field_index),
  CONSTRAINT uq_account_balance_key UNIQUE (company_id, observation_key),
  CONSTRAINT fk_account_balance_account_currency FOREIGN KEY (
    financial_account_id, company_id, currency_code)
    REFERENCES fincilia.financial_account (
      account_id, company_id, currency_code) ON DELETE RESTRICT,
  CONSTRAINT fk_account_balance_source FOREIGN KEY (source_record_id, company_id)
    REFERENCES fincilia.source_record (source_record_id, company_id)
    ON DELETE RESTRICT,
  CONSTRAINT ck_account_balance_field_digests CHECK (
    jsonb_typeof(field_digests) = 'object'
    AND field_digests ? 'amount'
    AND field_digests ? 'as_of'
    AND (field_digests ->> 'amount') ~ '^[0-9a-f]{64}$'
    AND (field_digests ->> 'as_of') ~ '^[0-9a-f]{64}$'
    AND pg_column_size(field_digests) <= 1024)
);

CREATE INDEX idx_account_balance_account_as_of
  ON fincilia.account_balance (
    company_id, financial_account_id, currency_code, as_of DESC);
CREATE INDEX idx_account_balance_source
  ON fincilia.account_balance (source_record_id);

-- Defensa en profundidad: una FK prueba identidad, no que la evidencia fuera
-- publicada ni que la cuenta siguiera vinculada a su fuente. El trigger falla
-- cerrado también ante una escritura runtime que no pase por la API.
CREATE FUNCTION fincilia.validate_account_balance_evidence()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, fincilia
AS $balance_guard$
DECLARE
  eligible boolean;
BEGIN
  SELECT EXISTS (
    SELECT 1
      FROM fincilia.source_record s
      JOIN fincilia.dataset_version d
        ON d.dataset_version_id = s.dataset_version_id
       AND d.company_id = s.company_id
      JOIN fincilia.data_source_account l
        ON l.data_source_id = s.data_source_id
       AND l.financial_account_id = NEW.financial_account_id
       AND l.company_id = s.company_id
     WHERE s.source_record_id = NEW.source_record_id
       AND s.company_id = NEW.company_id
       AND s.state = 'published'
       AND s.lineage_state = 'complete'
       AND d.state = 'published'
       AND d.completeness_state = 'verified'
       AND d.lineage_state = 'complete'
       AND l.status = 'active'
       AND l.valid_from <= (NEW.as_of AT TIME ZONE NEW.source_timezone)::date
       AND (l.valid_to IS NULL
            OR l.valid_to >= (NEW.as_of AT TIME ZONE NEW.source_timezone)::date)
  ) INTO eligible;
  IF NOT eligible THEN
    RAISE EXCEPTION 'account balance evidence is not eligible'
      USING ERRCODE = '23514', CONSTRAINT = 'ck_account_balance_evidence_eligible';
  END IF;
  RETURN NEW;
END
$balance_guard$;

REVOKE ALL ON FUNCTION fincilia.validate_account_balance_evidence() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fincilia.validate_account_balance_evidence()
  TO fincilia_app, fincilia_migrator;

CREATE TRIGGER account_balance_evidence_guard
  BEFORE INSERT ON fincilia.account_balance
  FOR EACH ROW EXECUTE FUNCTION fincilia.validate_account_balance_evidence();

ALTER TABLE fincilia.account_balance ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.account_balance FORCE ROW LEVEL SECURITY;
CREATE POLICY account_balance_isolation ON fincilia.account_balance
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

GRANT SELECT, INSERT ON fincilia.account_balance TO fincilia_app;
REVOKE UPDATE, DELETE ON fincilia.account_balance FROM fincilia_app;
REVOKE ALL PRIVILEGES ON fincilia.account_balance FROM fincilia_worker;

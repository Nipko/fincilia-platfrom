-- FNC-CLS-002 — correccion forward-only del guard de evidencia.
--
-- `valid_from` dice desde cuando el vinculo administrativo existe en Fincilia;
-- no demuestra desde cuando existia la cuenta en el mundo. Una fuente dada de
-- alta hoy puede aportar un extracto historico anterior. La autoridad que se
-- revalida al preparar es que el vinculo siga activo ahora; la fecha economica
-- permanece en la observacion y en su evidencia.

CREATE OR REPLACE FUNCTION fincilia.validate_account_balance_evidence()
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
       AND l.valid_to IS NULL
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

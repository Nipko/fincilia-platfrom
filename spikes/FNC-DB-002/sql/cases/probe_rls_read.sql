-- Con contexto de :company solo se ven las filas de :company.

\set ON_ERROR_STOP on

SET LOCAL fincilia.company_id = :'company';

DO $read$
DECLARE
  visible integer;
  foreign_rows integer;
BEGIN
  SELECT count(*) INTO visible FROM spike.company_ledger;
  SELECT count(*) INTO foreign_rows
  FROM spike.company_ledger
  WHERE company_id <> current_setting('fincilia.company_id', true);

  IF foreign_rows <> 0 THEN
    RAISE EXCEPTION 'FNC_SPIKE_RLS % sees % rows of another company',
      current_setting('fincilia.company_id', true), foreign_rows;
  END IF;
  IF visible <> 1 THEN
    RAISE EXCEPTION 'FNC_SPIKE_RLS expected exactly 1 own row, saw %', visible;
  END IF;

  RAISE NOTICE 'FNC_SPIKE_OK rls_read %', visible;
END
$read$;

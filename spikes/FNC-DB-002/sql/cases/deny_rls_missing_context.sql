-- Sin contexto de compania no se ve nada y no se puede escribir nada.
-- Primero se comprueba la lectura; despues la escritura, que debe abortar.

\set ON_ERROR_STOP on

DO $no_context$
DECLARE
  visible integer;
BEGIN
  SELECT count(*) INTO visible FROM spike.company_ledger;
  IF visible <> 0 THEN
    RAISE EXCEPTION 'FNC_SPIKE_RLS without company context % rows were visible', visible;
  END IF;
  RAISE NOTICE 'FNC_SPIKE_OK rls_no_context_read';
END
$no_context$;

INSERT INTO spike.company_ledger (company_id, description, amount, currency, occurred_on)
VALUES ('company-x', 'escritura sin contexto', 1.000000000000, 'COP', DATE '2026-01-31');

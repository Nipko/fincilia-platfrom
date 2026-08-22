-- Siembra una fila sintetica para :company con el contexto de esa compania.
-- Se ejecuta como runtime: si la politica no dejara escribir, este paso fallaria.

\set ON_ERROR_STOP on

SET LOCAL fincilia.company_id = :'company';

INSERT INTO spike.company_ledger (company_id, description, amount, currency, occurred_on)
VALUES (:'company', 'asiento sintetico de laboratorio', 1234.500000000000, 'COP', DATE '2026-01-31');

DO $seed$
BEGIN
  RAISE NOTICE 'FNC_SPIKE_OK seed %', current_setting('fincilia.company_id', true);
END
$seed$;

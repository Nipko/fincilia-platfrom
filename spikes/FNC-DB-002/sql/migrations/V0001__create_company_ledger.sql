-- V0001: tabla company-scoped sintetica con RLS forzada.
--
-- FORCE ROW LEVEL SECURITY somete tambien al propietario. Sin ella, el migrator
-- veria todas las companias y la prueba de aislamiento seria una ilusion.
--
-- La politica lee `fincilia.company_id` del contexto de sesion. Si no hay
-- contexto, `current_setting(..., true)` devuelve NULL, la comparacion es NULL y
-- la fila no pasa: falla cerrado, que es exactamente lo que se quiere probar.

CREATE TABLE spike.company_ledger (
  entry_id     bigint GENERATED ALWAYS AS IDENTITY,
  company_id   text NOT NULL,
  description  text NOT NULL,
  amount       numeric(38, 12) NOT NULL,
  currency     text NOT NULL CHECK (currency = 'COP'),
  occurred_on  date NOT NULL,
  CONSTRAINT pk_company_ledger PRIMARY KEY (company_id, entry_id)
);

ALTER TABLE spike.company_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE spike.company_ledger FORCE ROW LEVEL SECURITY;

CREATE POLICY company_isolation ON spike.company_ledger
  USING (company_id = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id = current_setting('fincilia.company_id', true));

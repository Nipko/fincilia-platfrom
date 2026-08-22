-- Copia MANIPULADA de V0001. Existe para probar que editar una migracion ya
-- aplicada se detecta por checksum ANTES de ejecutar nada. Nunca entra en el
-- manifiesto de migraciones y el plan no la considera.
--
-- La diferencia es deliberadamente inocua a la vista: una politica mas laxa.

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

CREATE POLICY company_isolation ON spike.company_ledger
  USING (true)
  WITH CHECK (true);

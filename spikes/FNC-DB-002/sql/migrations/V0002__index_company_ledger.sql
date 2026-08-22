-- V0002: indice de consulta por compania y fecha.
--
-- Deliberadamente SIN `CONCURRENTLY`: un indice concurrente no puede vivir
-- dentro de una transaccion, y el invariante que este spike prueba es
-- precisamente que cada migracion es atomica. La politica de indices
-- concurrentes en produccion es una decision aparte, no un efecto colateral.

CREATE INDEX idx_company_ledger_company_date
  ON spike.company_ledger (company_id, occurred_on);

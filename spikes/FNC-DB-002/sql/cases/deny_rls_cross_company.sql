-- Con contexto de :company, escribir una fila de :other debe fallar cerrado.

\set ON_ERROR_STOP on

SET LOCAL fincilia.company_id = :'company';

INSERT INTO spike.company_ledger (company_id, description, amount, currency, occurred_on)
VALUES (:'other', 'intento de escritura entre companias', 1.000000000000, 'COP', DATE '2026-01-31');

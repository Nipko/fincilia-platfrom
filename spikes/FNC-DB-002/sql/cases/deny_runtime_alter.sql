-- El runtime no puede alterar la estructura de una tabla que no le pertenece.
\set ON_ERROR_STOP on
ALTER TABLE spike.company_ledger ADD COLUMN runtime_should_not_add text;

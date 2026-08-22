-- Tampoco puede reescribir una fila ya registrada.
\set ON_ERROR_STOP on
UPDATE spike.schema_history SET checksum = repeat('0', 64);

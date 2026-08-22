-- El runtime no escribe el historial de migraciones: solo lo lee.
\set ON_ERROR_STOP on
INSERT INTO spike.schema_history (version, name, checksum, status)
VALUES ('V9999', 'runtime_forged', repeat('f', 64), 'applied');

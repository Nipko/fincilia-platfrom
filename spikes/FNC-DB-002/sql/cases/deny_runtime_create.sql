-- El runtime no puede crear objetos en el esquema del migrator.
\set ON_ERROR_STOP on
CREATE TABLE spike.runtime_should_not_create (id integer);

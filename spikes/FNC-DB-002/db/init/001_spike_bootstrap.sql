-- Bootstrap del laboratorio FNC-DB-002. Datos, roles y esquemas sinteticos.
--
-- Tres roles separados a proposito:
--   bootstrap : superusuario del contenedor, solo existe durante la creacion
--   migrator  : aplica migraciones y es propietario del esquema y del historial
--   runtime   : la aplicacion; no crea, no altera, no borra y no escribe historial
--
-- Ninguno de los dos ultimos es SUPERUSER, CREATEDB, CREATEROLE ni BYPASSRLS.

\set ON_ERROR_STOP on

REVOKE CREATE ON SCHEMA public FROM PUBLIC;

CREATE ROLE fnc_spike_migrator
  LOGIN
  PASSWORD 'fnc_spike_migrator_only'
  NOSUPERUSER
  NOCREATEDB
  NOCREATEROLE
  NOINHERIT
  NOBYPASSRLS;

CREATE ROLE fnc_spike_runtime
  LOGIN
  PASSWORD 'fnc_spike_runtime_only'
  NOSUPERUSER
  NOCREATEDB
  NOCREATEROLE
  NOINHERIT
  NOBYPASSRLS;

CREATE SCHEMA spike AUTHORIZATION fnc_spike_migrator;

-- El runtime entra al esquema pero no puede crear objetos en el.
GRANT USAGE ON SCHEMA spike TO fnc_spike_runtime;
REVOKE CREATE ON SCHEMA spike FROM fnc_spike_runtime;
REVOKE CREATE ON SCHEMA spike FROM PUBLIC;

-- Historial del spike: propiedad del migrator. El runtime solo lee.
CREATE TABLE spike.schema_history (
  version     text PRIMARY KEY,
  name        text NOT NULL,
  checksum    text NOT NULL CHECK (checksum ~ '^[0-9a-f]{64}$'),
  applied_at  timestamptz NOT NULL DEFAULT now(),
  applied_by  text NOT NULL DEFAULT current_user,
  status      text NOT NULL CHECK (status = 'applied')
);

ALTER TABLE spike.schema_history OWNER TO fnc_spike_migrator;
REVOKE ALL ON spike.schema_history FROM PUBLIC;
GRANT SELECT ON spike.schema_history TO fnc_spike_runtime;

-- Lo que cree el migrator queda utilizable por el runtime en DML, nunca en DDL.
ALTER DEFAULT PRIVILEGES FOR ROLE fnc_spike_migrator IN SCHEMA spike
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO fnc_spike_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE fnc_spike_migrator IN SCHEMA spike
  GRANT USAGE, SELECT ON SEQUENCES TO fnc_spike_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE fnc_spike_migrator IN SCHEMA spike
  REVOKE ALL ON TABLES FROM PUBLIC;

-- Marca del laboratorio: si alguien encuentra esta base fuera del spike, se ve.
CREATE TABLE spike.spike_environment (
  environment_id text PRIMARY KEY,
  data_class     text NOT NULL CHECK (data_class = 'synthetic_only'),
  purpose        text NOT NULL CHECK (purpose = 'migration_invariant_spike'),
  task_id        text NOT NULL CHECK (task_id = 'FNC-DB-002')
);
ALTER TABLE spike.spike_environment OWNER TO fnc_spike_migrator;
INSERT INTO spike.spike_environment (environment_id, data_class, purpose, task_id)
VALUES ('fincilia-db-spike-e0', 'synthetic_only', 'migration_invariant_spike', 'FNC-DB-002');
GRANT SELECT ON spike.spike_environment TO fnc_spike_runtime;

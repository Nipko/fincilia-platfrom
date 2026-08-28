#!/usr/bin/env bash
set -euo pipefail

: "${FINCILIA_DB_APP_PASSWORD:?missing app password}"
: "${FINCILIA_DB_MIGRATOR_PASSWORD:?missing migrator password}"
: "${FINCILIA_DB_WORKER_PASSWORD:?missing worker password}"

psql --set ON_ERROR_STOP=on \
  --set app_password="$FINCILIA_DB_APP_PASSWORD" \
  --set migrator_password="$FINCILIA_DB_MIGRATOR_PASSWORD" \
  --set worker_password="$FINCILIA_DB_WORKER_PASSWORD" \
  --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

SELECT format(
  'CREATE ROLE fincilia_app LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS',
  :'app_password'
) WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fincilia_app') \gexec

SELECT format(
  'CREATE ROLE fincilia_migrator LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS',
  :'migrator_password'
) WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fincilia_migrator') \gexec

SELECT format(
  'CREATE ROLE fincilia_worker LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS',
  :'worker_password'
) WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fincilia_worker') \gexec

CREATE ROLE fincilia_dispatch NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
  NOINHERIT NOBYPASSRLS;
CREATE ROLE fincilia_identity NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
  NOINHERIT NOBYPASSRLS;

GRANT fincilia_dispatch TO fincilia_migrator;
GRANT fincilia_identity TO fincilia_migrator;
GRANT CREATE ON DATABASE fincilia_beta TO fincilia_migrator;

CREATE SCHEMA IF NOT EXISTS app AUTHORIZATION fincilia_app;
CREATE SCHEMA IF NOT EXISTS platform AUTHORIZATION CURRENT_USER;
REVOKE ALL ON SCHEMA platform FROM PUBLIC;
GRANT USAGE ON SCHEMA platform TO fincilia_app;

CREATE TABLE IF NOT EXISTS platform.local_environment (
  environment_id text PRIMARY KEY,
  data_class text NOT NULL CHECK (data_class = 'synthetic_only'),
  purpose text NOT NULL CHECK (purpose = 'closed_beta_verification'),
  schema_contract_version text NOT NULL
);

INSERT INTO platform.local_environment VALUES
  ('fincilia-beta', 'synthetic_only', 'closed_beta_verification', '1.0.0')
ON CONFLICT (environment_id) DO NOTHING;

GRANT SELECT ON platform.local_environment TO fincilia_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA platform REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA platform REVOKE ALL ON SEQUENCES FROM PUBLIC;
SQL

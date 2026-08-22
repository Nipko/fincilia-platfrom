\set ON_ERROR_STOP on

REVOKE CREATE ON SCHEMA public FROM PUBLIC;

DO $bootstrap$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fincilia_app') THEN
    CREATE ROLE fincilia_app
      LOGIN
      PASSWORD 'fincilia_local_app_only'
      NOSUPERUSER
      NOCREATEDB
      NOCREATEROLE
      NOINHERIT
      NOBYPASSRLS;
  END IF;
END
$bootstrap$;

CREATE SCHEMA IF NOT EXISTS app AUTHORIZATION fincilia_app;
CREATE SCHEMA IF NOT EXISTS platform AUTHORIZATION CURRENT_USER;

REVOKE ALL ON SCHEMA platform FROM PUBLIC;
GRANT USAGE ON SCHEMA platform TO fincilia_app;

CREATE TABLE IF NOT EXISTS platform.local_environment (
  environment_id text PRIMARY KEY,
  data_class text NOT NULL CHECK (data_class = 'synthetic_only'),
  purpose text NOT NULL CHECK (purpose = 'local_platform_verification'),
  schema_contract_version text NOT NULL
);

INSERT INTO platform.local_environment (
  environment_id,
  data_class,
  purpose,
  schema_contract_version
) VALUES (
  'fincilia-local-e0',
  'synthetic_only',
  'local_platform_verification',
  '1.0.0'
) ON CONFLICT (environment_id) DO NOTHING;

GRANT SELECT ON platform.local_environment TO fincilia_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA platform REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA platform REVOKE ALL ON SEQUENCES FROM PUBLIC;


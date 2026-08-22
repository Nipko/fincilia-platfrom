-- Privilegios: ni migrator ni runtime pueden ser superusuario, saltarse RLS,
-- crear bases ni crear roles. Y el runtime nunca es propietario de una tabla.
-- Se ejecuta como bootstrap porque necesita leer el catalogo de roles.

\set ON_ERROR_STOP on

DO $privileges$
DECLARE
  role_row  record;
  owner_name text;
BEGIN
  FOR role_row IN
    SELECT rolname, rolsuper, rolbypassrls, rolcreatedb, rolcreaterole
    FROM pg_roles
    WHERE rolname IN ('fnc_spike_migrator', 'fnc_spike_runtime')
  LOOP
    IF role_row.rolsuper THEN
      RAISE EXCEPTION 'FNC_SPIKE_PRIVILEGE % is SUPERUSER', role_row.rolname;
    END IF;
    IF role_row.rolbypassrls THEN
      RAISE EXCEPTION 'FNC_SPIKE_PRIVILEGE % has BYPASSRLS', role_row.rolname;
    END IF;
    IF role_row.rolcreatedb THEN
      RAISE EXCEPTION 'FNC_SPIKE_PRIVILEGE % has CREATEDB', role_row.rolname;
    END IF;
    IF role_row.rolcreaterole THEN
      RAISE EXCEPTION 'FNC_SPIKE_PRIVILEGE % has CREATEROLE', role_row.rolname;
    END IF;
  END LOOP;

  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fnc_spike_migrator')
     OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fnc_spike_runtime') THEN
    RAISE EXCEPTION 'FNC_SPIKE_PRIVILEGE separated roles are missing';
  END IF;

  SELECT pg_get_userbyid(relowner) INTO owner_name
  FROM pg_class
  WHERE oid = 'spike.company_ledger'::regclass;

  IF owner_name <> 'fnc_spike_migrator' THEN
    RAISE EXCEPTION 'FNC_SPIKE_PRIVILEGE company_ledger owner is % , expected fnc_spike_migrator',
      owner_name;
  END IF;

  SELECT pg_get_userbyid(relowner) INTO owner_name
  FROM pg_class
  WHERE oid = 'spike.schema_history'::regclass;

  IF owner_name <> 'fnc_spike_migrator' THEN
    RAISE EXCEPTION 'FNC_SPIKE_PRIVILEGE schema_history owner is %', owner_name;
  END IF;

  RAISE NOTICE 'FNC_SPIKE_OK privileges';
END
$privileges$;

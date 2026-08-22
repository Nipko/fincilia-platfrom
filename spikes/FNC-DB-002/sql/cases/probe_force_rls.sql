-- FORCE RLS: la tabla sensible conserva RLS habilitada Y forzada.
-- Sin FORCE, el propietario queda exento y el aislamiento seria aparente.

\set ON_ERROR_STOP on

DO $force_rls$
DECLARE
  enabled boolean;
  forced  boolean;
  policies integer;
BEGIN
  SELECT relrowsecurity, relforcerowsecurity
  INTO enabled, forced
  FROM pg_class
  WHERE oid = 'spike.company_ledger'::regclass;

  IF NOT enabled THEN
    RAISE EXCEPTION 'FNC_SPIKE_RLS company_ledger does not have row level security enabled';
  END IF;
  IF NOT forced THEN
    RAISE EXCEPTION 'FNC_SPIKE_RLS company_ledger does not FORCE row level security';
  END IF;

  SELECT count(*) INTO policies
  FROM pg_policies
  WHERE schemaname = 'spike' AND tablename = 'company_ledger';

  IF policies < 1 THEN
    RAISE EXCEPTION 'FNC_SPIKE_RLS company_ledger has row level security without any policy';
  END IF;

  RAISE NOTICE 'FNC_SPIKE_OK force_rls';
END
$force_rls$;

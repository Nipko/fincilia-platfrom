\set ON_ERROR_STOP on

CREATE ROLE fincilia_app
  LOGIN
  PASSWORD 'fincilia_spike_app'
  NOSUPERUSER
  NOCREATEDB
  NOCREATEROLE
  NOINHERIT
  NOBYPASSRLS;

CREATE SCHEMA control;
CREATE SCHEMA demo;
CREATE SCHEMA platform;

CREATE TABLE control.company (
  id uuid PRIMARY KEY,
  name text NOT NULL
);

CREATE TABLE control.subject (
  id uuid PRIMARY KEY,
  display_name text NOT NULL
);

CREATE TABLE control.company_grant (
  company_id uuid NOT NULL REFERENCES control.company(id),
  subject_id uuid NOT NULL REFERENCES control.subject(id),
  can_create boolean NOT NULL DEFAULT false,
  revoked_at timestamptz,
  PRIMARY KEY (company_id, subject_id)
);

CREATE TABLE demo.reconciliation_probe (
  company_id uuid NOT NULL REFERENCES control.company(id),
  id uuid NOT NULL,
  label text NOT NULL CHECK (length(label) BETWEEN 1 AND 120),
  created_by uuid NOT NULL REFERENCES control.subject(id),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (company_id, id)
);

CREATE TABLE platform.outbox_event (
  company_id uuid NOT NULL REFERENCES control.company(id),
  id uuid NOT NULL,
  aggregate_type text NOT NULL,
  aggregate_id uuid NOT NULL,
  event_type text NOT NULL,
  payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (company_id, id)
);

ALTER TABLE control.company_grant ENABLE ROW LEVEL SECURITY;
ALTER TABLE control.company_grant FORCE ROW LEVEL SECURITY;
ALTER TABLE demo.reconciliation_probe ENABLE ROW LEVEL SECURITY;
ALTER TABLE demo.reconciliation_probe FORCE ROW LEVEL SECURITY;
ALTER TABLE platform.outbox_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.outbox_event FORCE ROW LEVEL SECURITY;

CREATE POLICY company_grant_context ON control.company_grant
  FOR SELECT
  TO fincilia_app
  USING (
    company_id = nullif(current_setting('app.company_id', true), '')::uuid
    AND subject_id = nullif(current_setting('app.subject_id', true), '')::uuid
    AND revoked_at IS NULL
  );

CREATE POLICY probe_company_context ON demo.reconciliation_probe
  FOR ALL
  TO fincilia_app
  USING (
    company_id = nullif(current_setting('app.company_id', true), '')::uuid
    AND EXISTS (
      SELECT 1
      FROM control.company_grant AS grant_row
      WHERE grant_row.company_id = reconciliation_probe.company_id
        AND grant_row.subject_id = nullif(current_setting('app.subject_id', true), '')::uuid
        AND grant_row.can_create
        AND grant_row.revoked_at IS NULL
    )
  )
  WITH CHECK (
    company_id = nullif(current_setting('app.company_id', true), '')::uuid
    AND created_by = nullif(current_setting('app.subject_id', true), '')::uuid
    AND EXISTS (
      SELECT 1
      FROM control.company_grant AS grant_row
      WHERE grant_row.company_id = reconciliation_probe.company_id
        AND grant_row.subject_id = created_by
        AND grant_row.can_create
        AND grant_row.revoked_at IS NULL
    )
  );

CREATE POLICY outbox_company_context ON platform.outbox_event
  FOR ALL
  TO fincilia_app
  USING (
    company_id = nullif(current_setting('app.company_id', true), '')::uuid
    AND EXISTS (
      SELECT 1
      FROM control.company_grant AS grant_row
      WHERE grant_row.company_id = outbox_event.company_id
        AND grant_row.subject_id = nullif(current_setting('app.subject_id', true), '')::uuid
        AND grant_row.can_create
        AND grant_row.revoked_at IS NULL
    )
  )
  WITH CHECK (
    company_id = nullif(current_setting('app.company_id', true), '')::uuid
    AND EXISTS (
      SELECT 1
      FROM control.company_grant AS grant_row
      WHERE grant_row.company_id = outbox_event.company_id
        AND grant_row.subject_id = nullif(current_setting('app.subject_id', true), '')::uuid
        AND grant_row.can_create
        AND grant_row.revoked_at IS NULL
    )
  );

GRANT USAGE ON SCHEMA control, demo, platform TO fincilia_app;
GRANT SELECT ON control.company_grant TO fincilia_app;
GRANT SELECT, INSERT ON demo.reconciliation_probe TO fincilia_app;
GRANT SELECT, INSERT ON platform.outbox_event TO fincilia_app;

INSERT INTO control.company (id, name) VALUES
  ('10000000-0000-4000-8000-000000000001', 'Empresa Sintética Uno'),
  ('10000000-0000-4000-8000-000000000002', 'Empresa Sintética Dos');

INSERT INTO control.subject (id, display_name) VALUES
  ('20000000-0000-4000-8000-000000000001', 'Contador Sintético Uno'),
  ('20000000-0000-4000-8000-000000000002', 'Contador Sintético Dos');

INSERT INTO control.company_grant (company_id, subject_id, can_create) VALUES
  ('10000000-0000-4000-8000-000000000001', '20000000-0000-4000-8000-000000000001', true),
  ('10000000-0000-4000-8000-000000000002', '20000000-0000-4000-8000-000000000002', true);

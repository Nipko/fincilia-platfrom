\set ON_ERROR_STOP on

CREATE ROLE fincilia_app
  LOGIN PASSWORD 'fincilia_auth_spike_app'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;

CREATE ROLE fincilia_event_worker
  LOGIN PASSWORD 'fincilia_event_worker_spike'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;

CREATE SCHEMA control;
CREATE SCHEMA clean;
CREATE SCHEMA platform;

CREATE TABLE control.company (
  id uuid PRIMARY KEY,
  name text NOT NULL,
  authorization_version bigint NOT NULL DEFAULT 1 CHECK (authorization_version > 0)
);

CREATE TABLE control.principal (
  id uuid PRIMARY KEY,
  display_name text NOT NULL
);

CREATE TABLE control.engagement (
  id uuid PRIMARY KEY,
  company_id uuid NOT NULL REFERENCES control.company(id),
  organization_label text NOT NULL,
  state text NOT NULL CHECK (state IN ('active', 'revoked'))
);

CREATE TABLE control.accounting_operator_assignment (
  id uuid PRIMARY KEY,
  company_id uuid NOT NULL REFERENCES control.company(id),
  engagement_id uuid NOT NULL REFERENCES control.engagement(id),
  operator_role text NOT NULL CHECK (operator_role IN ('primary_accounting_operator', 'collaborator')),
  active boolean NOT NULL DEFAULT true,
  UNIQUE (company_id, engagement_id, operator_role)
);

CREATE UNIQUE INDEX one_active_primary_accounting_operator_per_company
  ON control.accounting_operator_assignment (company_id)
  WHERE operator_role = 'primary_accounting_operator' AND active;

CREATE TABLE control.company_grant (
  company_id uuid NOT NULL REFERENCES control.company(id),
  principal_id uuid NOT NULL REFERENCES control.principal(id),
  purpose text NOT NULL CHECK (purpose IN ('reconciliation.prepare', 'portfolio.read')),
  can_publish boolean NOT NULL DEFAULT false,
  revoked_at timestamptz,
  PRIMARY KEY (company_id, principal_id, purpose)
);

CREATE TABLE control.issued_authorization_context (
  id uuid PRIMARY KEY,
  company_id uuid NOT NULL REFERENCES control.company(id),
  principal_id uuid NOT NULL REFERENCES control.principal(id),
  purpose text NOT NULL,
  authorization_version bigint NOT NULL CHECK (authorization_version > 0),
  issued_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz,
  CHECK (expires_at > issued_at)
);

CREATE TABLE clean.synthetic_record (
  company_id uuid NOT NULL REFERENCES control.company(id),
  id uuid NOT NULL,
  label text NOT NULL CHECK (length(label) BETWEEN 1 AND 120),
  created_by uuid NOT NULL REFERENCES control.principal(id),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (company_id, id)
);

CREATE TABLE platform.outbox_event (
  company_id uuid NOT NULL REFERENCES control.company(id),
  id uuid NOT NULL,
  event_type text NOT NULL,
  aggregate_id uuid NOT NULL,
  payload jsonb NOT NULL,
  payload_digest text NOT NULL CHECK (payload_digest ~ '^[0-9a-f]{64}$'),
  occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'published')),
  attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
  lease_owner text,
  lease_expires_at timestamptz,
  lock_version bigint NOT NULL DEFAULT 0 CHECK (lock_version >= 0),
  published_at timestamptz,
  PRIMARY KEY (company_id, id),
  UNIQUE (company_id, event_type, aggregate_id)
);

CREATE TABLE platform.inbox_receipt (
  company_id uuid NOT NULL REFERENCES control.company(id),
  consumer_id text NOT NULL,
  event_id uuid NOT NULL,
  event_digest text NOT NULL CHECK (event_digest ~ '^[0-9a-f]{64}$'),
  received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (company_id, consumer_id, event_id)
);

CREATE TABLE platform.synthetic_consumer_effect (
  company_id uuid NOT NULL REFERENCES control.company(id),
  consumer_id text NOT NULL,
  event_id uuid NOT NULL,
  applied_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (company_id, consumer_id, event_id),
  FOREIGN KEY (company_id, consumer_id, event_id)
    REFERENCES platform.inbox_receipt(company_id, consumer_id, event_id)
);

ALTER TABLE clean.synthetic_record ENABLE ROW LEVEL SECURITY;
ALTER TABLE clean.synthetic_record FORCE ROW LEVEL SECURITY;
ALTER TABLE platform.outbox_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.outbox_event FORCE ROW LEVEL SECURITY;

CREATE FUNCTION control.active_context_valid(expected_company uuid, expected_publish boolean)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, control
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM control.issued_authorization_context AS issued
    JOIN control.company AS company ON company.id = issued.company_id
    JOIN control.company_grant AS grant_row
      ON grant_row.company_id = issued.company_id
     AND grant_row.principal_id = issued.principal_id
     AND grant_row.purpose = issued.purpose
    WHERE issued.id = nullif(current_setting('app.authorization_context_id', true), '')::uuid
      AND issued.company_id = expected_company
      AND issued.principal_id = nullif(current_setting('app.principal_id', true), '')::uuid
      AND issued.purpose = nullif(current_setting('app.purpose', true), '')
      AND issued.authorization_version = company.authorization_version
      AND issued.revoked_at IS NULL
      AND issued.issued_at <= statement_timestamp()
      AND issued.expires_at > statement_timestamp()
      AND grant_row.revoked_at IS NULL
      AND (NOT expected_publish OR grant_row.can_publish)
  )
$$;

CREATE FUNCTION control.activate_authorization_context(
  requested_context uuid,
  requested_company uuid,
  requested_principal uuid,
  requested_purpose text
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, control
AS $$
BEGIN
  PERFORM set_config('app.authorization_context_id', requested_context::text, true);
  PERFORM set_config('app.company_id', requested_company::text, true);
  PERFORM set_config('app.principal_id', requested_principal::text, true);
  PERFORM set_config('app.purpose', requested_purpose, true);

  IF NOT control.active_context_valid(requested_company, true) THEN
    RAISE EXCEPTION 'authorization context is invalid, stale, expired, revoked or insufficient'
      USING ERRCODE = '42501';
  END IF;
END
$$;

CREATE POLICY synthetic_record_context ON clean.synthetic_record
  FOR ALL TO fincilia_app
  USING (control.active_context_valid(company_id, false))
  WITH CHECK (
    control.active_context_valid(company_id, true)
    AND created_by = nullif(current_setting('app.principal_id', true), '')::uuid
  );

CREATE POLICY outbox_context ON platform.outbox_event
  FOR ALL TO fincilia_app
  USING (control.active_context_valid(company_id, false))
  WITH CHECK (control.active_context_valid(company_id, true));

CREATE FUNCTION platform.consume_synthetic_event(
  requested_company uuid,
  requested_consumer text,
  requested_event uuid,
  requested_digest text
)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, platform
AS $$
DECLARE
  existing_digest text;
  inserted_count integer;
BEGIN
  IF requested_consumer !~ '^[a-z0-9._-]{3,80}$'
     OR requested_digest !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION 'invalid consumer or digest' USING ERRCODE = '22023';
  END IF;

  INSERT INTO platform.inbox_receipt (company_id, consumer_id, event_id, event_digest)
  VALUES (requested_company, requested_consumer, requested_event, requested_digest)
  ON CONFLICT (company_id, consumer_id, event_id) DO NOTHING;
  GET DIAGNOSTICS inserted_count = ROW_COUNT;

  IF inserted_count = 0 THEN
    SELECT event_digest INTO STRICT existing_digest
    FROM platform.inbox_receipt
    WHERE company_id = requested_company
      AND consumer_id = requested_consumer
      AND event_id = requested_event;
    IF existing_digest <> requested_digest THEN
      RAISE EXCEPTION 'event identity reused with different digest' USING ERRCODE = '23505';
    END IF;
    RETURN 'replayed';
  END IF;

  INSERT INTO platform.synthetic_consumer_effect (company_id, consumer_id, event_id)
  VALUES (requested_company, requested_consumer, requested_event);
  RETURN 'applied';
END
$$;

CREATE FUNCTION platform.claim_outbox(requested_worker text, lease_seconds integer)
RETURNS TABLE (
  company_id uuid,
  event_id uuid,
  event_type text,
  payload jsonb,
  payload_digest text,
  lock_version bigint
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, platform
AS $$
BEGIN
  IF requested_worker !~ '^[a-z0-9._-]{3,80}$' OR lease_seconds NOT BETWEEN 5 AND 300 THEN
    RAISE EXCEPTION 'invalid worker or lease' USING ERRCODE = '22023';
  END IF;

  RETURN QUERY
  WITH candidate AS (
    SELECT candidate_event.company_id, candidate_event.id
      FROM platform.outbox_event AS candidate_event
     WHERE candidate_event.status = 'pending'
        OR (candidate_event.status = 'processing'
            AND candidate_event.lease_expires_at <= clock_timestamp())
     ORDER BY candidate_event.occurred_at, candidate_event.id
     FOR UPDATE SKIP LOCKED
     LIMIT 1
  )
  UPDATE platform.outbox_event AS claimed
     SET status = 'processing',
         attempt_count = claimed.attempt_count + 1,
         lease_owner = requested_worker,
         lease_expires_at = clock_timestamp() + make_interval(secs => lease_seconds),
         lock_version = claimed.lock_version + 1
    FROM candidate
   WHERE claimed.company_id = candidate.company_id AND claimed.id = candidate.id
  RETURNING claimed.company_id, claimed.id, claimed.event_type, claimed.payload,
            claimed.payload_digest, claimed.lock_version;
END
$$;

CREATE FUNCTION platform.ack_outbox(
  requested_worker text,
  requested_company uuid,
  requested_event uuid,
  expected_lock_version bigint
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, platform
AS $$
BEGIN
  UPDATE platform.outbox_event
     SET status = 'published',
         published_at = clock_timestamp(),
         lease_owner = NULL,
         lease_expires_at = NULL
   WHERE company_id = requested_company
     AND id = requested_event
     AND status = 'processing'
     AND lease_owner = requested_worker
     AND lease_expires_at > clock_timestamp()
     AND lock_version = expected_lock_version;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'stale or invalid outbox acknowledgement' USING ERRCODE = '40001';
  END IF;
END
$$;

REVOKE ALL ON FUNCTION control.active_context_valid(uuid, boolean) FROM PUBLIC;
REVOKE ALL ON FUNCTION control.activate_authorization_context(uuid, uuid, uuid, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform.consume_synthetic_event(uuid, text, uuid, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform.claim_outbox(text, integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform.ack_outbox(text, uuid, uuid, bigint) FROM PUBLIC;

GRANT USAGE ON SCHEMA control, clean, platform TO fincilia_app;
GRANT EXECUTE ON FUNCTION control.active_context_valid(uuid, boolean) TO fincilia_app;
GRANT EXECUTE ON FUNCTION control.activate_authorization_context(uuid, uuid, uuid, text) TO fincilia_app;
GRANT USAGE ON SCHEMA platform TO fincilia_event_worker;
GRANT EXECUTE ON FUNCTION platform.consume_synthetic_event(uuid, text, uuid, text) TO fincilia_event_worker;
GRANT EXECUTE ON FUNCTION platform.claim_outbox(text, integer) TO fincilia_event_worker;
GRANT EXECUTE ON FUNCTION platform.ack_outbox(text, uuid, uuid, bigint) TO fincilia_event_worker;
GRANT SELECT, INSERT ON clean.synthetic_record TO fincilia_app;
GRANT SELECT, INSERT ON platform.outbox_event TO fincilia_app;

INSERT INTO control.company (id, name) VALUES
  ('10000000-0000-4000-8000-000000000001', 'Synthetic Company One'),
  ('10000000-0000-4000-8000-000000000002', 'Synthetic Company Two');

INSERT INTO control.principal (id, display_name) VALUES
  ('20000000-0000-4000-8000-000000000001', 'Synthetic Preparer One'),
  ('20000000-0000-4000-8000-000000000002', 'Synthetic Preparer Two');

INSERT INTO control.company_grant (company_id, principal_id, purpose, can_publish) VALUES
  ('10000000-0000-4000-8000-000000000001', '20000000-0000-4000-8000-000000000001', 'reconciliation.prepare', true),
  ('10000000-0000-4000-8000-000000000002', '20000000-0000-4000-8000-000000000002', 'reconciliation.prepare', true);

INSERT INTO control.issued_authorization_context
  (id, company_id, principal_id, purpose, authorization_version, expires_at)
VALUES
  ('30000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001', '20000000-0000-4000-8000-000000000001', 'reconciliation.prepare', 1, '2099-01-01T00:00:00Z'),
  ('30000000-0000-4000-8000-000000000002', '10000000-0000-4000-8000-000000000002', '20000000-0000-4000-8000-000000000002', 'reconciliation.prepare', 1, '2099-01-01T00:00:00Z');

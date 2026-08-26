\set ON_ERROR_STOP on

CREATE ROLE fnc_concurrency_owner NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
CREATE ROLE fnc_concurrency_runtime LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
CREATE SCHEMA fnc_lab AUTHORIZATION fnc_concurrency_owner;

SET ROLE fnc_concurrency_owner;

CREATE TABLE fnc_lab.work_item (
  work_id text PRIMARY KEY,
  state text NOT NULL CHECK (state IN ('queued', 'running', 'succeeded')),
  fencing_counter bigint NOT NULL DEFAULT 0 CHECK (fencing_counter >= 0),
  lease_owner text,
  lease_token bigint,
  lease_expires_at timestamptz,
  CHECK ((state = 'running') =
    (lease_owner IS NOT NULL AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL))
);

CREATE TABLE fnc_lab.work_execution (
  work_id text NOT NULL REFERENCES fnc_lab.work_item(work_id),
  fencing_token bigint NOT NULL CHECK (fencing_token > 0),
  claimed_by text NOT NULL,
  claimed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (work_id, fencing_token)
);

CREATE TABLE fnc_lab.domain_effect (
  work_id text PRIMARY KEY REFERENCES fnc_lab.work_item(work_id),
  fencing_token bigint NOT NULL,
  effect_value text NOT NULL,
  committed_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE fnc_lab.outbox_event (
  event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  work_id text NOT NULL UNIQUE REFERENCES fnc_lab.domain_effect(work_id),
  fencing_token bigint NOT NULL,
  state text NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'delivered')),
  delivery_attempts integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  delivered_at timestamptz
);

CREATE TABLE fnc_lab.delivery_receipt (
  event_id bigint PRIMARY KEY REFERENCES fnc_lab.outbox_event(event_id),
  dispatcher text NOT NULL,
  delivered_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE FUNCTION fnc_lab.claim_work(p_worker text, p_lease_ms integer)
RETURNS TABLE(work_id text, fencing_token bigint)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, fnc_lab
AS $claim$
DECLARE
  selected_work text;
  selected_token bigint;
BEGIN
  IF p_worker !~ '^[a-z0-9._-]{3,40}$' OR p_lease_ms NOT BETWEEN 100 AND 60000 THEN
    RAISE EXCEPTION 'invalid claim request' USING ERRCODE = '22023';
  END IF;
  SELECT item.work_id INTO selected_work
    FROM fnc_lab.work_item item
   WHERE item.state = 'queued'
      OR (item.state = 'running' AND item.lease_expires_at <= clock_timestamp())
   ORDER BY item.work_id
   FOR UPDATE SKIP LOCKED
   LIMIT 1;
  IF selected_work IS NULL THEN
    RETURN;
  END IF;
  UPDATE fnc_lab.work_item item
     SET state = 'running', fencing_counter = item.fencing_counter + 1,
         lease_owner = p_worker, lease_token = item.fencing_counter + 1,
         lease_expires_at = clock_timestamp() +
           make_interval(secs => p_lease_ms::double precision / 1000.0)
   WHERE item.work_id = selected_work
   RETURNING item.lease_token INTO selected_token;
  INSERT INTO fnc_lab.work_execution(work_id, fencing_token, claimed_by)
  VALUES (selected_work, selected_token, p_worker);
  RETURN QUERY SELECT selected_work, selected_token;
END;
$claim$;

CREATE FUNCTION fnc_lab.commit_effect(
  p_worker text, p_work_id text, p_fencing_token bigint,
  p_effect_value text, p_fail_after_domain boolean DEFAULT false
) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, fnc_lab
AS $commit$
DECLARE
  current_item fnc_lab.work_item%ROWTYPE;
  existing_effect fnc_lab.domain_effect%ROWTYPE;
BEGIN
  SELECT * INTO existing_effect FROM fnc_lab.domain_effect effect
   WHERE effect.work_id = p_work_id;
  IF FOUND THEN
    IF existing_effect.fencing_token = p_fencing_token
       AND existing_effect.effect_value = p_effect_value THEN
      RETURN 'replayed';
    END IF;
    RETURN 'effect_conflict';
  END IF;
  SELECT * INTO current_item FROM fnc_lab.work_item item
   WHERE item.work_id = p_work_id FOR UPDATE;
  IF NOT FOUND OR current_item.state <> 'running'
     OR current_item.lease_owner IS DISTINCT FROM p_worker
     OR current_item.lease_token IS DISTINCT FROM p_fencing_token
     OR current_item.lease_expires_at <= clock_timestamp() THEN
    RETURN 'stale_lease';
  END IF;
  INSERT INTO fnc_lab.domain_effect(work_id, fencing_token, effect_value)
  VALUES (p_work_id, p_fencing_token, p_effect_value);
  IF p_fail_after_domain THEN
    RAISE EXCEPTION 'synthetic failure after domain insert' USING ERRCODE = 'P0001';
  END IF;
  INSERT INTO fnc_lab.outbox_event(work_id, fencing_token)
  VALUES (p_work_id, p_fencing_token);
  UPDATE fnc_lab.work_item
     SET state = 'succeeded', lease_owner = NULL,
         lease_token = NULL, lease_expires_at = NULL
   WHERE work_id = p_work_id;
  RETURN 'committed';
END;
$commit$;

CREATE FUNCTION fnc_lab.claim_outbox(p_dispatcher text)
RETURNS TABLE(event_id bigint)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, fnc_lab
AS $outbox$
DECLARE selected_event bigint;
BEGIN
  IF p_dispatcher !~ '^[a-z0-9._-]{3,40}$' THEN
    RAISE EXCEPTION 'invalid dispatcher' USING ERRCODE = '22023';
  END IF;
  SELECT event.event_id INTO selected_event
    FROM fnc_lab.outbox_event event
   WHERE event.state = 'pending'
   ORDER BY event.event_id
   FOR UPDATE SKIP LOCKED
   LIMIT 1;
  IF selected_event IS NULL THEN RETURN; END IF;
  UPDATE fnc_lab.outbox_event
     SET delivery_attempts = delivery_attempts + 1
   WHERE outbox_event.event_id = selected_event;
  RETURN QUERY SELECT selected_event;
END;
$outbox$;

CREATE FUNCTION fnc_lab.ack_outbox(p_event_id bigint, p_dispatcher text)
RETURNS text
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, fnc_lab
AS $ack$
DECLARE inserted_count integer;
BEGIN
  INSERT INTO fnc_lab.delivery_receipt(event_id, dispatcher)
  VALUES (p_event_id, p_dispatcher)
  ON CONFLICT (event_id) DO NOTHING;
  GET DIAGNOSTICS inserted_count = ROW_COUNT;
  UPDATE fnc_lab.outbox_event
     SET state = 'delivered', delivered_at = COALESCE(delivered_at, clock_timestamp())
   WHERE event_id = p_event_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'event unavailable' USING ERRCODE = '22023'; END IF;
  RETURN CASE WHEN inserted_count = 1 THEN 'delivered' ELSE 'replayed' END;
END;
$ack$;

RESET ROLE;

REVOKE ALL ON SCHEMA fnc_lab FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA fnc_lab FROM PUBLIC, fnc_concurrency_runtime;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA fnc_lab FROM PUBLIC, fnc_concurrency_runtime;
GRANT USAGE ON SCHEMA fnc_lab TO fnc_concurrency_runtime;
GRANT EXECUTE ON FUNCTION fnc_lab.claim_work(text, integer) TO fnc_concurrency_runtime;
GRANT EXECUTE ON FUNCTION fnc_lab.commit_effect(text, text, bigint, text, boolean)
  TO fnc_concurrency_runtime;
GRANT EXECUTE ON FUNCTION fnc_lab.claim_outbox(text) TO fnc_concurrency_runtime;
GRANT EXECUTE ON FUNCTION fnc_lab.ack_outbox(bigint, text) TO fnc_concurrency_runtime;

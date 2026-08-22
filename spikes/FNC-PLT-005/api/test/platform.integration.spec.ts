import { randomUUID } from 'node:crypto';
import { Pool } from 'pg';
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';
import {
  AuthorizationRequest,
  EventWorkerBoundary,
  PlatformBoundary,
  sha256,
} from '../src/platform';

const COMPANY_ONE = '10000000-0000-4000-8000-000000000001';
const COMPANY_TWO = '10000000-0000-4000-8000-000000000002';
const PRINCIPAL_ONE = '20000000-0000-4000-8000-000000000001';
const CONTEXT_ONE = '30000000-0000-4000-8000-000000000001';

const DATABASE_URL =
  process.env.DATABASE_URL ??
  'postgresql://fincilia_app:fincilia_auth_spike_app@127.0.0.1:55433/fincilia_auth_spike';
const ADMIN_DATABASE_URL =
  process.env.ADMIN_DATABASE_URL ??
  'postgresql://postgres:fincilia_auth_spike_admin@127.0.0.1:55433/fincilia_auth_spike';
const EVENT_WORKER_DATABASE_URL =
  process.env.EVENT_WORKER_DATABASE_URL ??
  'postgresql://fincilia_event_worker:fincilia_event_worker_spike@127.0.0.1:55433/fincilia_auth_spike';

const AUTHORIZATION: AuthorizationRequest = {
  contextId: CONTEXT_ONE,
  companyId: COMPANY_ONE,
  principalId: PRINCIPAL_ONE,
  purpose: 'reconciliation.prepare',
};

describe('FNC-PLT-005 authorization and event boundary', () => {
  const platform = new PlatformBoundary(DATABASE_URL);
  const eventConsumer = new EventWorkerBoundary(EVENT_WORKER_DATABASE_URL);
  const admin = new Pool({ connectionString: ADMIN_DATABASE_URL, max: 4 });
  const eventWorkers = new Pool({ connectionString: EVENT_WORKER_DATABASE_URL, max: 4 });

  beforeAll(async () => {
    await admin.query('SELECT 1');
  });

  beforeEach(async () => {
    await admin.query(`
      TRUNCATE platform.synthetic_consumer_effect, platform.inbox_receipt,
        platform.outbox_event, clean.synthetic_record,
        control.accounting_operator_assignment, control.engagement;
      UPDATE control.company SET authorization_version = 1;
      UPDATE control.company_grant SET revoked_at = NULL, can_publish = true;
      UPDATE control.issued_authorization_context
         SET authorization_version = 1,
             purpose = 'reconciliation.prepare',
             issued_at = clock_timestamp() - interval '1 minute',
             expires_at = '2099-01-01T00:00:00Z',
             revoked_at = NULL;
    `);
  });

  afterAll(async () => {
    await platform.close();
    await eventConsumer.close();
    await eventWorkers.end();
    await admin.end();
  });

  it('TST-RLS-001 reads and writes only the authorized company', async () => {
    await platform.publishSyntheticRecord(AUTHORIZATION, `allowed-${Date.now()}`);

    const visible = await platform.withAuthorization(AUTHORIZATION, (client) =>
      client.query<{ company_id: string }>(
        'SELECT company_id FROM clean.synthetic_record ORDER BY created_at',
      ),
    );
    expect(visible.rows.map((row) => row.company_id)).toEqual([COMPANY_ONE]);

    await expect(
      platform.withAuthorization(AUTHORIZATION, (client) =>
        client.query(
          `INSERT INTO clean.synthetic_record (company_id, id, label, created_by)
           VALUES ($1, $2, 'cross-company-denied', $3)`,
          [COMPANY_TWO, randomUUID(), PRINCIPAL_ONE],
        ),
      ),
    ).rejects.toMatchObject({ code: '42501' });
  });

  it('TST-RLS-002 clears SET LOCAL context when a pooled connection is reused', async () => {
    await platform.publishSyntheticRecord(AUTHORIZATION, `pool-${Date.now()}`);
    expect(await platform.visibleRecordCountWithoutContext()).toBe(0);
  });

  it('TST-AUTH-001 rejects a context after authorization_version changes', async () => {
    await admin.query(
      'UPDATE control.company SET authorization_version = authorization_version + 1 WHERE id = $1',
      [COMPANY_ONE],
    );
    await expect(
      platform.publishSyntheticRecord(AUTHORIZATION, 'stale-context'),
    ).rejects.toMatchObject({ code: '42501' });
  });

  it('TST-AUTH-002 rejects revoked, expired and purpose-mismatched contexts', async () => {
    await admin.query(
      'UPDATE control.issued_authorization_context SET revoked_at = clock_timestamp() WHERE id = $1',
      [CONTEXT_ONE],
    );
    await expect(platform.publishSyntheticRecord(AUTHORIZATION, 'revoked')).rejects.toMatchObject({
      code: '42501',
    });

    await admin.query(
      `UPDATE control.issued_authorization_context
          SET revoked_at = NULL,
              issued_at = clock_timestamp() - interval '2 hours',
              expires_at = clock_timestamp() - interval '1 hour'
        WHERE id = $1`,
      [CONTEXT_ONE],
    );
    await expect(platform.publishSyntheticRecord(AUTHORIZATION, 'expired')).rejects.toMatchObject({
      code: '42501',
    });

    await admin.query(
      `UPDATE control.issued_authorization_context
          SET issued_at = clock_timestamp() - interval '1 minute',
              expires_at = '2099-01-01T00:00:00Z'
        WHERE id = $1`,
      [CONTEXT_ONE],
    );
    await expect(
      platform.publishSyntheticRecord(
        { ...AUTHORIZATION, purpose: 'portfolio.read' },
        'wrong-purpose',
      ),
    ).rejects.toMatchObject({ code: '42501' });
  });

  it('TST-TEN-001-N09 enforces one active primary operator under concurrency', async () => {
    const engagementOne = randomUUID();
    const engagementTwo = randomUUID();
    await admin.query(
      `INSERT INTO control.engagement (id, company_id, organization_label, state)
       VALUES ($1, $3, 'Synthetic Firm One', 'active'),
              ($2, $3, 'Synthetic Firm Two', 'active')`,
      [engagementOne, engagementTwo, COMPANY_ONE],
    );

    const insertPrimary = (engagementId: string) =>
      admin.query(
        `INSERT INTO control.accounting_operator_assignment
           (id, company_id, engagement_id, operator_role, active)
         VALUES ($1, $2, $3, 'primary_accounting_operator', true)`,
        [randomUUID(), COMPANY_ONE, engagementId],
      );
    const outcomes = await Promise.allSettled([
      insertPrimary(engagementOne),
      insertPrimary(engagementTwo),
    ]);

    expect(outcomes.filter((outcome) => outcome.status === 'fulfilled')).toHaveLength(1);
    expect(outcomes.filter((outcome) => outcome.status === 'rejected')).toHaveLength(1);
    const count = await admin.query<{ count: string }>(
      `SELECT count(*)::text AS count
         FROM control.accounting_operator_assignment
        WHERE company_id = $1
          AND operator_role = 'primary_accounting_operator'
          AND active`,
      [COMPANY_ONE],
    );
    expect(count.rows[0].count).toBe('1');
  });

  it('TST-OUT-001 commits the record and outbox event in one transaction', async () => {
    const created = await platform.publishSyntheticRecord(AUTHORIZATION, `atomic-${Date.now()}`);
    const counts = await admin.query<{ records: string; events: string }>(
      `SELECT
         (SELECT count(*)::text FROM clean.synthetic_record WHERE id = $1) AS records,
         (SELECT count(*)::text FROM platform.outbox_event WHERE id = $2) AS events`,
      [created.recordId, created.eventId],
    );
    expect(counts.rows[0]).toEqual({ records: '1', events: '1' });
  });

  it('TST-OUT-002 rolls back the record and event after a failure', async () => {
    const label = `rollback-${Date.now()}`;
    await expect(
      platform.publishSyntheticRecord(AUTHORIZATION, label, { failAfterOutbox: true }),
    ).rejects.toThrow('synthetic failure after outbox');
    const counts = await admin.query<{ records: string; events: string }>(
      `SELECT
         (SELECT count(*)::text FROM clean.synthetic_record WHERE label = $1) AS records,
         (SELECT count(*)::text FROM platform.outbox_event WHERE payload->>'label' = $1) AS events`,
      [label],
    );
    expect(counts.rows[0]).toEqual({ records: '0', events: '0' });
  });

  it('TST-INB-001 applies concurrent duplicate deliveries once', async () => {
    const eventId = randomUUID();
    const digest = sha256('synthetic-event-one');
    const outcomes = await Promise.all([
      eventConsumer.consumeExactlyOnce(COMPANY_ONE, 'projection.synthetic', eventId, digest),
      eventConsumer.consumeExactlyOnce(COMPANY_ONE, 'projection.synthetic', eventId, digest),
    ]);
    expect(outcomes.sort()).toEqual(['applied', 'replayed']);
    expect(
      await eventConsumer.consumeExactlyOnce(
        COMPANY_ONE,
        'projection.synthetic',
        eventId,
        digest,
      ),
    ).toBe('replayed');

    const effects = await admin.query<{ count: string }>(
      `SELECT count(*)::text AS count
         FROM platform.synthetic_consumer_effect
        WHERE company_id = $1 AND consumer_id = 'projection.synthetic' AND event_id = $2`,
      [COMPANY_ONE, eventId],
    );
    expect(effects.rows[0].count).toBe('1');
  });

  it('TST-INB-002 rejects an event identity reused with different content', async () => {
    const eventId = randomUUID();
    await eventConsumer.consumeExactlyOnce(
      COMPANY_ONE,
      'projection.synthetic',
      eventId,
      sha256('first'),
    );
    await expect(
      eventConsumer.consumeExactlyOnce(
        COMPANY_ONE,
        'projection.synthetic',
        eventId,
        sha256('different'),
      ),
    ).rejects.toMatchObject({ code: '23505' });
  });

  it('TST-RET-001 allows only one concurrent claim and fences stale ACKs', async () => {
    await platform.publishSyntheticRecord(AUTHORIZATION, `claim-${Date.now()}`);
    const claim = () =>
      eventWorkers.query<{
        company_id: string;
        event_id: string;
        lock_version: string;
      }>('SELECT * FROM platform.claim_outbox($1, $2)', ['worker.synthetic', 60]);

    const [first, second] = await Promise.all([claim(), claim()]);
    const claimedRows = [...first.rows, ...second.rows];
    expect(claimedRows).toHaveLength(1);
    const claimed = claimedRows[0];

    await eventWorkers.query('SELECT platform.ack_outbox($1, $2, $3, $4)', [
      'worker.synthetic',
      claimed.company_id,
      claimed.event_id,
      claimed.lock_version,
    ]);
    await expect(
      eventWorkers.query('SELECT platform.ack_outbox($1, $2, $3, $4)', [
        'worker.synthetic',
        claimed.company_id,
        claimed.event_id,
        claimed.lock_version,
      ]),
    ).rejects.toMatchObject({ code: '40001' });
  });

  it('TST-DB-001 keeps the application role non-owner and FORCE RLS enabled', async () => {
    const role = await admin.query<{
      rolname: string;
      rolsuper: boolean;
      rolbypassrls: boolean;
    }>(
      `SELECT rolname, rolsuper, rolbypassrls
         FROM pg_roles
        WHERE rolname IN ('fincilia_app', 'fincilia_event_worker')
        ORDER BY rolname`,
    );
    expect(role.rows).toEqual([
      { rolname: 'fincilia_app', rolsuper: false, rolbypassrls: false },
      { rolname: 'fincilia_event_worker', rolsuper: false, rolbypassrls: false },
    ]);

    const tables = await admin.query<{ relname: string; relforcerowsecurity: boolean }>(
      `SELECT relname, relforcerowsecurity
         FROM pg_class
        WHERE oid IN ('clean.synthetic_record'::regclass, 'platform.outbox_event'::regclass)
        ORDER BY relname`,
    );
    expect(tables.rows).toEqual([
      { relname: 'outbox_event', relforcerowsecurity: true },
      { relname: 'synthetic_record', relforcerowsecurity: true },
    ]);
  });
});

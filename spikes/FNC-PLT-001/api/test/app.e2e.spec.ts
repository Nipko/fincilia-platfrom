import 'reflect-metadata';
import { INestApplication } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import { Pool } from 'pg';
import request from 'supertest';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { AppModule } from '../src/app.module';
import { DbService } from '../src/db.service';
import { RecordsService } from '../src/records.service';

const COMPANY_ONE = '10000000-0000-4000-8000-000000000001';
const COMPANY_TWO = '10000000-0000-4000-8000-000000000002';
const SUBJECT_ONE = '20000000-0000-4000-8000-000000000001';
const ADMIN_DATABASE_URL =
  process.env.ADMIN_DATABASE_URL ??
  'postgresql://postgres:fincilia_spike_admin@127.0.0.1:55432/fincilia_spike';

describe('FNC-PLT-001 synthetic walking spike', () => {
  let app: INestApplication;
  let db: DbService;
  let records: RecordsService;
  const adminPool = new Pool({ connectionString: ADMIN_DATABASE_URL });

  beforeAll(async () => {
    const moduleRef = await Test.createTestingModule({ imports: [AppModule] }).compile();
    app = moduleRef.createNestApplication();
    await app.init();
    db = app.get(DbService);
    records = app.get(RecordsService);
  });

  afterAll(async () => {
    await app.close();
    await adminPool.end();
  });

  it('TST-RLS-001 verifies the server-side grant and creates in the authorized company', async () => {
    const label = `authorized-${Date.now()}`;
    const response = await request(app.getHttpServer())
      .post(`/companies/${COMPANY_ONE}/records`)
      .set('x-subject-id', SUBJECT_ONE)
      .send({ label })
      .expect(201);

    expect(response.body).toMatchObject({ companyId: COMPANY_ONE, label });
    expect(response.body.id).toMatch(/^[0-9a-f-]{36}$/i);
  });

  it('TST-RLS-002 denies a subject that has no grant for the requested company', async () => {
    await request(app.getHttpServer())
      .post(`/companies/${COMPANY_TWO}/records`)
      .set('x-subject-id', SUBJECT_ONE)
      .send({ label: 'must-not-exist' })
      .expect(403);
  });

  it('TST-RLS-002 leaves no company context in the reused application pool', async () => {
    expect(await db.countVisibleWithoutContext()).toBe(0);
  });

  it('TST-OUT-001 commits the domain row and outbox event atomically', async () => {
    const created = await records.createSyntheticRecord(
      SUBJECT_ONE,
      COMPANY_ONE,
      `atomic-success-${Date.now()}`,
    );
    const result = await adminPool.query<{ records: string; events: string }>(
      `SELECT
         (SELECT count(*)::text FROM demo.reconciliation_probe WHERE id = $1) AS records,
         (SELECT count(*)::text FROM platform.outbox_event WHERE id = $2) AS events`,
      [created.id, created.outboxEventId],
    );
    expect(result.rows[0]).toEqual({ records: '1', events: '1' });
  });

  it('TST-OUT-001 rolls back both rows after a synthetic failure', async () => {
    const label = `atomic-rollback-${Date.now()}`;
    await expect(
      records.createSyntheticRecord(SUBJECT_ONE, COMPANY_ONE, label, {
        failAfterOutbox: true,
      }),
    ).rejects.toThrow('synthetic failure after outbox insert');

    const result = await adminPool.query<{ records: string; events: string }>(
      `SELECT
         (SELECT count(*)::text FROM demo.reconciliation_probe WHERE label = $1) AS records,
         (SELECT count(*)::text FROM platform.outbox_event WHERE payload->>'label' = $1) AS events`,
      [label],
    );
    expect(result.rows[0]).toEqual({ records: '0', events: '0' });
  });
});

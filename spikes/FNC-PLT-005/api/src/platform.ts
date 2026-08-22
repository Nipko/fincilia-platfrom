import { createHash, randomUUID } from 'node:crypto';
import { Pool, PoolClient } from 'pg';

export interface AuthorizationRequest {
  contextId: string;
  companyId: string;
  principalId: string;
  purpose: string;
}
export interface Publication {
  recordId: string;
  eventId: string;
}

export class PlatformBoundary {
  readonly appPool: Pool;

  constructor(databaseUrl: string) {
    this.appPool = new Pool({ connectionString: databaseUrl, max: 4 });
  }

  async close(): Promise<void> {
    await this.appPool.end();
  }

  async withAuthorization<T>(
    request: AuthorizationRequest,
    operation: (client: PoolClient) => Promise<T>,
  ): Promise<T> {
    const client = await this.appPool.connect();
    try {
      await client.query('BEGIN');
      await client.query(
        'SELECT control.activate_authorization_context($1, $2, $3, $4)',
        [request.contextId, request.companyId, request.principalId, request.purpose],
      );
      const result = await operation(client);
      await client.query('COMMIT');
      return result;
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally {
      client.release();
    }
  }

  async publishSyntheticRecord(
    request: AuthorizationRequest,
    label: string,
    options: { failAfterOutbox?: boolean } = {},
  ): Promise<Publication> {
    return this.withAuthorization(request, async (client) => {
      const recordId = randomUUID();
      const eventId = randomUUID();
      const payload = { record_id: recordId, label, synthetic: true };
      const payloadDigest = sha256(canonicalJson(payload));

      await client.query(
        `INSERT INTO clean.synthetic_record (company_id, id, label, created_by)
         VALUES ($1, $2, $3, $4)`,
        [request.companyId, recordId, label, request.principalId],
      );
      await client.query(
        `INSERT INTO platform.outbox_event
           (company_id, id, event_type, aggregate_id, payload, payload_digest)
         VALUES ($1, $2, 'clean.synthetic-record.published.v1', $3, $4::jsonb, $5)`,
        [request.companyId, eventId, recordId, JSON.stringify(payload), payloadDigest],
      );
      if (options.failAfterOutbox) {
        throw new Error('synthetic failure after outbox');
      }
      return { recordId, eventId };
    });
  }

  async visibleRecordCountWithoutContext(): Promise<number> {
    const result = await this.appPool.query<{ count: string }>(
      'SELECT count(*)::text AS count FROM clean.synthetic_record',
    );
    return Number(result.rows[0].count);
  }

}

export class EventWorkerBoundary {
  private readonly pool: Pool;

  constructor(databaseUrl: string) {
    this.pool = new Pool({ connectionString: databaseUrl, max: 4 });
  }

  async close(): Promise<void> {
    await this.pool.end();
  }

  async consumeExactlyOnce(
    companyId: string,
    consumerId: string,
    eventId: string,
    eventDigest: string,
  ): Promise<'applied' | 'replayed'> {
    const client = await this.pool.connect();
    try {
      await client.query('BEGIN');
      const result = await client.query<{ outcome: 'applied' | 'replayed' }>(
        'SELECT platform.consume_synthetic_event($1, $2, $3, $4) AS outcome',
        [companyId, consumerId, eventId, eventDigest],
      );
      await client.query('COMMIT');
      return result.rows[0].outcome;
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally {
      client.release();
    }
  }
}

export function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map(canonicalJson).join(',')}]`;
  }
  if (value !== null && typeof value === 'object') {
    return `{${Object.entries(value as Record<string, unknown>)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, item]) => `${JSON.stringify(key)}:${canonicalJson(item)}`)
      .join(',')}}`;
  }
  return JSON.stringify(value);
}

export function sha256(value: string): string {
  return createHash('sha256').update(value, 'utf8').digest('hex');
}

import { ForbiddenException, Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool, PoolClient } from 'pg';

const DEFAULT_DATABASE_URL =
  'postgresql://fincilia_app:fincilia_spike_app@127.0.0.1:55432/fincilia_spike';

@Injectable()
export class DbService implements OnModuleDestroy {
  private readonly pool = new Pool({
    connectionString: process.env.DATABASE_URL ?? DEFAULT_DATABASE_URL,
    max: 2,
  });

  async withVerifiedCompany<T>(
    subjectId: string,
    companyId: string,
    operation: (client: PoolClient) => Promise<T>,
  ): Promise<T> {
    const client = await this.pool.connect();
    try {
      await client.query('BEGIN');
      await client.query("SELECT set_config('app.subject_id', $1, true)", [subjectId]);
      await client.query("SELECT set_config('app.company_id', $1, true)", [companyId]);

      const authorization = await client.query<{ can_create: boolean }>(
        `SELECT can_create
           FROM control.company_grant
          WHERE subject_id = $1
            AND company_id = $2
            AND revoked_at IS NULL`,
        [subjectId, companyId],
      );
      if (authorization.rowCount !== 1 || !authorization.rows[0].can_create) {
        throw new ForbiddenException('No active synthetic grant for this company');
      }

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

  async countVisibleWithoutContext(): Promise<number> {
    const result = await this.pool.query<{ count: string }>(
      'SELECT count(*)::text AS count FROM demo.reconciliation_probe',
    );
    return Number(result.rows[0].count);
  }

  async onModuleDestroy(): Promise<void> {
    await this.pool.end();
  }
}

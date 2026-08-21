import { Injectable } from '@nestjs/common';
import { randomUUID } from 'node:crypto';
import { DbService } from './db.service';

export interface CreatedProbe {
  companyId: string;
  id: string;
  label: string;
  outboxEventId: string;
}

@Injectable()
export class RecordsService {
  constructor(private readonly db: DbService) {}

  async createSyntheticRecord(
    subjectId: string,
    companyId: string,
    label: string,
    options: { failAfterOutbox?: boolean } = {},
  ): Promise<CreatedProbe> {
    return this.db.withVerifiedCompany(subjectId, companyId, async (client) => {
      const id = randomUUID();
      const outboxEventId = randomUUID();

      await client.query(
        `INSERT INTO demo.reconciliation_probe (company_id, id, label, created_by)
         VALUES ($1, $2, $3, $4)`,
        [companyId, id, label, subjectId],
      );
      await client.query(
        `INSERT INTO platform.outbox_event
           (company_id, id, aggregate_type, aggregate_id, event_type, payload)
         VALUES ($1, $2, 'reconciliation_probe', $3, 'probe.created', $4::jsonb)`,
        [companyId, outboxEventId, id, JSON.stringify({ id, label, synthetic: true })],
      );

      if (options.failAfterOutbox) {
        throw new Error('synthetic failure after outbox insert');
      }

      return { companyId, id, label, outboxEventId };
    });
  }
}

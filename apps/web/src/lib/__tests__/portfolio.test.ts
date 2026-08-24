import { describe, expect, it, vi } from 'vitest';

vi.mock('server-only', () => ({}));

import { ApiError, type CompanySummary, type Expectation } from '../api';
import {
  loadCompanySnapshot,
  mapWithConcurrency,
  summarizeDatasets,
  summarizeExpectations,
} from '../portfolio';

const COMPANY: CompanySummary = {
  company_id: 'company-synthetic-a',
  legal_name: 'Empresa Sintetica A',
  country_code: 'CO',
  status: 'active',
  roles: ['accountant'],
};

function expectation(overrides: Partial<Expectation>): Expectation {
  return {
    expectation_id: 'expectation-synthetic',
    data_source_id: 'source-synthetic',
    period_start: '2026-08-01',
    period_end: '2026-08-31',
    due_on: '2026-08-27',
    late_after: '2026-08-28',
    state: 'pending',
    stored_state: 'pending',
    days_late: 0,
    source_name: 'Banco sintetico',
    waived_reason: null,
    ...overrides,
  };
}

function client(permissions = ['document.read', 'movement.read']) {
  return {
    fetchCompany: vi.fn().mockResolvedValue({
      ...COMPANY,
      firm_id: 'firm-synthetic',
      engagement_id: 'engagement-synthetic',
      authorization_version: 3,
      permissions,
    }),
    fetchDocuments: vi.fn().mockResolvedValue([]),
    fetchDatasets: vi.fn().mockResolvedValue([]),
    fetchExpectations: vi.fn().mockResolvedValue([]),
  };
}

describe('portfolio operativo', () => {
  it('cuenta estados de trabajo sin agregar importes ni inferir conciliacion', () => {
    const metric = summarizeDatasets([
      { state: 'validated' },
      { state: 'staging' },
      { state: 'published' },
      { state: 'rejected' },
    ] as never);

    expect(metric).toEqual({
      state: 'available',
      value: { visible: 4, pendingReview: 1, partial: 1, published: 1 },
    });
    expect(JSON.stringify(metric)).not.toMatch(/amount|balance|match/i);
  });

  it('separa vencidas, proximas y pendientes usando el atraso del servidor', () => {
    const metric = summarizeExpectations(
      [
        expectation({ expectation_id: 'late', days_late: 2 }),
        expectation({ expectation_id: 'soon', due_on: '2026-08-29' }),
        expectation({ expectation_id: 'later', due_on: '2026-09-20' }),
        expectation({ expectation_id: 'received', stored_state: 'received' }),
      ],
      '2026-08-24',
    );

    expect(metric).toEqual({
      state: 'available',
      value: { overdue: 1, dueSoon: 1, pending: 3 },
    });
  });

  it('no consulta ni presenta como cero una metrica sin permiso', async () => {
    const api = client([]);

    const snapshot = await loadCompanySnapshot(
      'token-synthetic',
      COMPANY,
      '2026-08-24',
      api,
    );

    expect(snapshot.documents).toEqual({ state: 'restricted' });
    expect(snapshot.datasets).toEqual({ state: 'restricted' });
    expect(snapshot.expectations).toEqual({ state: 'restricted' });
    expect(api.fetchDocuments).not.toHaveBeenCalled();
    expect(api.fetchDatasets).not.toHaveBeenCalled();
  });

  it('conserva un 403 de carrera de revocacion como restringido, no como cero', async () => {
    const api = client();
    api.fetchDatasets.mockRejectedValue(new ApiError(403, 'forbidden'));

    const snapshot = await loadCompanySnapshot(
      'token-synthetic',
      COMPANY,
      '2026-08-24',
      api,
    );

    expect(snapshot.access).toBe('available');
    expect(snapshot.datasets).toEqual({ state: 'restricted' });
    expect(snapshot.documents).toEqual({
      state: 'available',
      value: { visible: 0, quarantine: 0 },
    });
  });

  it('marca una empresa revocada y preserva la expiracion global de sesion', async () => {
    const revoked = client();
    revoked.fetchCompany.mockRejectedValue(new ApiError(404, 'hidden'));
    const snapshot = await loadCompanySnapshot(
      'token-synthetic',
      COMPANY,
      '2026-08-24',
      revoked,
    );
    expect(snapshot.access).toBe('revoked');
    expect(snapshot.documents.state).toBe('restricted');

    const expired = client();
    expired.fetchCompany.mockRejectedValue(new ApiError(401, 'expired'));
    await expect(
      loadCompanySnapshot('token-synthetic', COMPANY, '2026-08-24', expired),
    ).rejects.toMatchObject({ status: 401 });
  });

  it('limita concurrencia, conserva orden y procesa todo el portafolio', async () => {
    let active = 0;
    let peak = 0;
    const result = await mapWithConcurrency([0, 1, 2, 3, 4, 5], 3, async (item) => {
      active += 1;
      peak = Math.max(peak, active);
      await new Promise((resolve) => setTimeout(resolve, 2));
      active -= 1;
      return item * 2;
    });

    expect(peak).toBeLessThanOrEqual(3);
    expect(result).toEqual([0, 2, 4, 6, 8, 10]);
  });
});

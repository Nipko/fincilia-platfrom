import { describe, expect, it, vi } from 'vitest';

vi.mock('server-only', () => ({}));

import {
  ApiError,
  type CloseReadinessResult,
  type CompanySummary,
} from '../api';
import {
  aggregateCloseReadinessCounts,
  availableClosePeriods,
  filterCloseReadinessPeriod,
  formatClosePeriod,
  loadCloseReadinessCompany,
  selectCloseReadinessCompanies,
  selectClosePeriod,
} from '../close-readiness';

const COMPANY: CompanySummary = {
  company_id: 'company-synthetic-a',
  legal_name: 'Empresa Sintetica A',
  country_code: 'CO',
  status: 'active',
  roles: ['reviewer'],
};

const RESULT: CloseReadinessResult = {
  mode: 'diagnostic_only',
  close_ready: false,
  can_execute_close: false,
  period_count: 1,
  blocked_period_count: 1,
  source_count: 2,
  limit: 12,
  notice: 'diagnostic_only',
  items: [{
    period_start: '2026-07-01',
    period_end: '2026-07-31',
    status: 'blocked',
    close_ready: false,
    can_execute_close: false,
    source_count: 2,
    selected_dataset_count: 1,
    controls: [
      { code: 'reconciliation_reviews', state: 'blocked', count: 3, detail: 'Abiertas' },
      { code: 'quality_alerts', state: 'blocked', count: 2, detail: 'Altas' },
      { code: 'pending_corrections', state: 'blocked', count: 1, detail: 'Pendientes' },
      { code: 'account_balances', state: 'unavailable', count: 1, detail: 'Ausente' },
    ],
    blockers: [
      { code: 'account_balances', count: 1, detail: 'Ausente' },
      { code: 'product_close', count: 1, detail: 'Deshabilitado' },
    ],
    sources: [],
  }],
};

function client(permissions = ['report.read']) {
  return {
    fetchCompany: vi.fn().mockResolvedValue({
      ...COMPANY,
      firm_id: 'firm-synthetic',
      engagement_id: 'engagement-synthetic',
      authorization_version: 1,
      permissions,
    }),
    fetchCloseReadiness: vi.fn().mockResolvedValue(RESULT),
  };
}

describe('preparacion diagnostica de cierre', () => {
  it('solo selecciona empresas presentes en la sesion', () => {
    expect(selectCloseReadinessCompanies([COMPANY], COMPANY.company_id)).toEqual([COMPANY]);
    expect(selectCloseReadinessCompanies([COMPANY], 'company-foreign')).toEqual([COMPANY]);
    expect(selectCloseReadinessCompanies([COMPANY], ['company-synthetic-a']))
      .toEqual([COMPANY]);
  });

  it('no consulta el diagnostico sin report.read', async () => {
    const api = client([]);
    await expect(loadCloseReadinessCompany('token', COMPANY, api))
      .resolves.toMatchObject({ access: 'restricted', result: null });
    expect(api.fetchCloseReadiness).not.toHaveBeenCalled();
  });

  it('distingue revocacion, indisponibilidad y sesion expirada', async () => {
    const revoked = client();
    revoked.fetchCompany.mockRejectedValue(new ApiError(404, 'hidden'));
    await expect(loadCloseReadinessCompany('token', COMPANY, revoked))
      .resolves.toMatchObject({ access: 'revoked', result: null });

    const unavailable = client();
    unavailable.fetchCloseReadiness.mockRejectedValue(new ApiError(503, 'down'));
    await expect(loadCloseReadinessCompany('token', COMPANY, unavailable))
      .resolves.toMatchObject({ access: 'unavailable', result: null });

    const expired = client();
    expired.fetchCloseReadiness.mockRejectedValue(new ApiError(401, 'expired'));
    await expect(loadCloseReadinessCompany('token', COMPANY, expired))
      .rejects.toMatchObject({ status: 401 });
  });

  it('agrega solo conteos de trabajo y conserva el cierre denegado', async () => {
    const snapshot = await loadCloseReadinessCompany('token', COMPANY, client());
    expect(snapshot.result?.close_ready).toBe(false);
    expect(snapshot.result?.can_execute_close).toBe(false);
    const totals = aggregateCloseReadinessCounts([snapshot]);
    expect(totals).toEqual({
      periods: 1,
      blockedPeriods: 1,
      sources: 2,
      openReviews: 3,
      highAlerts: 2,
      pendingCorrections: 1,
    });
    expect(JSON.stringify(totals)).not.toMatch(/amount|balance|currency|close_ready/i);
  });

  it('formatea periodos sin reinterpretar la zona horaria', () => {
    expect(formatClosePeriod('2026-07-01', '2026-07-31'))
      .toMatch(/1.*jul.*2026.*31.*jul.*2026/i);
  });

  it('filtra solo periodos descubiertos en respuestas autorizadas', async () => {
    const snapshot = await loadCloseReadinessCompany('token', COMPANY, client());
    const available = availableClosePeriods([snapshot]);
    expect(available).toEqual([{
      key: '2026-07-01:2026-07-31', start: '2026-07-01', end: '2026-07-31',
    }]);
    expect(selectClosePeriod(available, 'foreign:period')).toBe('todos');
    const selected = selectClosePeriod(available, available[0]?.key);
    const filtered = filterCloseReadinessPeriod([snapshot], selected);
    expect(filtered[0]?.result).toMatchObject({
      period_count: 1, blocked_period_count: 1, source_count: 2,
    });
    expect(filterCloseReadinessPeriod([snapshot], '2025-01-01:2025-01-31')[0]
      ?.result).toMatchObject({ period_count: 0, source_count: 0 });
  });
});

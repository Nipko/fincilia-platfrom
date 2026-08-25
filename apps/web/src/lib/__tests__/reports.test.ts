import { describe, expect, it, vi } from 'vitest';

vi.mock('server-only', () => ({}));

import { ApiError, type CompanySummary, type OperationalReport } from '../api';
import {
  aggregateOperationalCounts,
  loadCompanyReport,
  parseReportDate,
  parseReportDays,
  reportHref,
  selectReportCompanies,
} from '../reports';

const COMPANY: CompanySummary = {
  company_id: 'company-synthetic-a', legal_name: 'Empresa A', country_code: 'CO',
  status: 'active', roles: ['preparer'],
};

const REPORT: OperationalReport = {
  range: { days: 90, start: '2026-05-27', end: '2026-08-24', timezone: 'UTC' },
  summary: {
    documents: { total: 4, accepted: 3, quarantined: 1, bytes: 1024 },
    datasets: { total: 3, draft: 1, validated: 0, published: 2, rejected: 0,
      records: 30, movements: 29, rejected_records: 1,
      completeness_mismatch: 0, completeness_unknown: 1, lineage_invalidated: 0 },
    reconciliation: { candidates: 2, pending: 1, confirmed: 1, rejected: 0 },
    quality: { signals: 3, open: 1, acknowledged: 1, closed: 1, active_high: 1 },
  },
  activity_series: [{ month: '2026-08-01', documents: 4, datasets: 3, movements: 29 }],
  money_totals: [{ currency: 'COP', movement_count: 29,
    inflow_amount: '100.000000000000', outflow_amount: '20.000000000000' }],
  money_series: [{ month: '2026-08-01', currency: 'COP', movement_count: 29,
    inflow_amount: '100.000000000000', outflow_amount: '20.000000000000' }],
  recent_datasets: [], notice: 'operational_non_certified',
};

function client(permissions = ['report.read']) {
  return {
    fetchCompany: vi.fn().mockResolvedValue({ ...COMPANY, firm_id: 'firm',
      engagement_id: 'engagement', authorization_version: 1, permissions }),
    fetchOperationalReport: vi.fn().mockResolvedValue(REPORT),
  };
}

describe('centro de informes', () => {
  it('cierra vocabularios de rango fecha y empresa', () => {
    expect(parseReportDays('365')).toBe(365);
    expect(parseReportDays('31')).toBe(90);
    expect(parseReportDate('2026-08-24', '2026-08-24')).toBe('2026-08-24');
    expect(parseReportDate('2026-08-25', '2026-08-24')).toBeUndefined();
    expect(parseReportDate('2026-02-31', '2026-08-24')).toBeUndefined();
    expect(selectReportCompanies([COMPANY], 'foreign')).toEqual([COMPANY]);
  });

  it('separa lectura exportacion y restriccion', async () => {
    await expect(loadCompanyReport('token', COMPANY, 90, undefined, client()))
      .resolves.toMatchObject({ access: 'available', canExport: false, report: REPORT });
    await expect(loadCompanyReport('token', COMPANY, 90, undefined,
      client(['report.read', 'report.export'])))
      .resolves.toMatchObject({ access: 'available', canExport: true });
    const restricted = client([]);
    await expect(loadCompanyReport('token', COMPANY, 90, undefined, restricted))
      .resolves.toMatchObject({ access: 'restricted', report: null });
    expect(restricted.fetchOperationalReport).not.toHaveBeenCalled();
  });

  it('no vuelve cero una revocacion y propaga expiracion', async () => {
    const revoked = client();
    revoked.fetchCompany.mockRejectedValue(new ApiError(403, 'denied'));
    await expect(loadCompanyReport('token', COMPANY, 90, undefined, revoked))
      .resolves.toMatchObject({ access: 'revoked', report: null });
    const expired = client();
    expired.fetchOperationalReport.mockRejectedValue(new ApiError(401, 'expired'));
    await expect(loadCompanyReport('token', COMPANY, 90, undefined, expired))
      .rejects.toMatchObject({ status: 401 });
  });

  it('agrega solo conteos y conserva importes fuera del agregado', () => {
    const totals = aggregateOperationalCounts([{ company: COMPANY,
      access: 'available', canExport: true, report: REPORT }]);
    expect(totals).toEqual({ documents: 4, datasets: 3, movements: 29,
      pendingReviews: 1, activeHigh: 1 });
    expect(JSON.stringify(totals)).not.toMatch(/amount|inflow|outflow|currency/i);
    expect(reportHref(COMPANY.company_id, 90, '2026-08-24')).toBe(
      '/api/companies/company-synthetic-a/reports/operational?days=90&as_of=2026-08-24');
  });
});

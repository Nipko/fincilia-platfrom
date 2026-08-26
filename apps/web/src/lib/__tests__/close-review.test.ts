import { describe, expect, it, vi } from 'vitest';

vi.mock('server-only', () => ({}));

import { ApiError, type CompanySummary } from '../api';
import { loadCloseReviewCompany, packetsForPeriod } from '../close-review';

const COMPANY: CompanySummary = {
  company_id: '161b0037-c445-50aa-b400-72632d3f53f0',
  legal_name: 'Empresa sintetica', country_code: 'CO', status: 'active',
  roles: ['preparer'],
};

function client(permissions = ['report.read', 'close.prepare']) {
  return {
    fetchCompany: vi.fn().mockResolvedValue({
      ...COMPANY, firm_id: 'firm-synthetic', engagement_id: 'engagement-synthetic',
      authorization_version: 1, permissions,
    }),
    fetchCloseReviewPackets: vi.fn().mockResolvedValue({
      items: [], has_more: false, limit: 100, financial_effect: 'none',
      certifies_close: false, can_execute_close: false,
    }),
    fetchCloseReviewers: vi.fn().mockResolvedValue([{
      subject_id: '21111111-1111-4111-8111-111111111111',
      display_name: 'Revisor sintetico', company_roles: ['reviewer'],
    }]),
  };
}

describe('expedientes de revision previa', () => {
  it('consulta revisores solo cuando el servidor concede close.prepare', async () => {
    const preparer = client();
    await expect(loadCloseReviewCompany('token', COMPANY, preparer))
      .resolves.toMatchObject({ access: 'available', reviewers: [{ company_roles: ['reviewer'] }] });
    expect(preparer.fetchCloseReviewers).toHaveBeenCalledOnce();

    const reviewer = client(['report.read', 'close.approve']);
    await expect(loadCloseReviewCompany('token', COMPANY, reviewer))
      .resolves.toMatchObject({ access: 'available', reviewers: [] });
    expect(reviewer.fetchCloseReviewers).not.toHaveBeenCalled();
  });

  it('no trata una revocacion o una caida como lista vacia disponible', async () => {
    const revoked = client();
    revoked.fetchCompany.mockRejectedValue(new ApiError(404, 'hidden'));
    await expect(loadCloseReviewCompany('token', COMPANY, revoked))
      .resolves.toMatchObject({ access: 'revoked', packets: [] });

    const unavailable = client();
    unavailable.fetchCloseReviewPackets.mockRejectedValue(new ApiError(503, 'down'));
    await expect(loadCloseReviewCompany('token', COMPANY, unavailable))
      .resolves.toMatchObject({ access: 'unavailable', packets: [] });
  });

  it('propaga la sesion expirada y no consulta sin report.read', async () => {
    const expired = client();
    expired.fetchCompany.mockRejectedValue(new ApiError(401, 'expired'));
    await expect(loadCloseReviewCompany('token', COMPANY, expired))
      .rejects.toMatchObject({ status: 401 });

    const restricted = client([]);
    await expect(loadCloseReviewCompany('token', COMPANY, restricted))
      .resolves.toMatchObject({ access: 'restricted' });
    expect(restricted.fetchCloseReviewPackets).not.toHaveBeenCalled();
  });

  it('filtra expedientes por ambas fechas exactas', () => {
    const packet = {
      period_start: '2026-07-01', period_end: '2026-07-31', packet_id: 'packet-a',
    };
    const snapshot = {
      company: COMPANY, access: 'available' as const, permissions: [], reviewers: [],
      packets: [packet] as never[],
    };
    expect(packetsForPeriod(snapshot, '2026-07-01', '2026-07-31')).toHaveLength(1);
    expect(packetsForPeriod(snapshot, '2026-07-01', '2026-08-31')).toHaveLength(0);
  });
});

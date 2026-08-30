import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => {
  class ApiError extends Error {
    readonly status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  }
  return {
    ApiError,
    readSession: vi.fn(),
    fetchMe: vi.fn(),
    fetchOverview: vi.fn(),
    fetchIdentities: vi.fn(),
    fetchOrganizations: vi.fn(),
    fetchDiagnostics: vi.fn(),
    fetchAudit: vi.fn(),
    redirect: vi.fn((): never => { throw new Error('NEXT_REDIRECT'); }),
  };
});

vi.mock('next/navigation', () => ({ redirect: mocks.redirect }));
vi.mock('@/lib/session', () => ({ readSession: mocks.readSession }));
vi.mock('@/lib/api', () => ({
  ApiError: mocks.ApiError,
  fetchMe: mocks.fetchMe,
  fetchPlatformOverview: mocks.fetchOverview,
  fetchPlatformIdentities: mocks.fetchIdentities,
  fetchPlatformOrganizations: mocks.fetchOrganizations,
  fetchPlatformDiagnostics: mocks.fetchDiagnostics,
  fetchPlatformAudit: mocks.fetchAudit,
}));
vi.mock('../actions', () => ({
  changeIdentityStatus: vi.fn(), grantRole: vi.fn(), revokeRole: vi.fn(),
}));

import PlatformPage from '../page';

describe('PlatformPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.readSession.mockResolvedValue({ token: 'session', displayName: 'Founder' });
    mocks.fetchMe.mockResolvedValue({
      subject_id: '11111111-1111-4111-8111-111111111111',
      display_name: 'Founder',
      platform_roles: ['platform_superadmin'],
      companies: [],
    });
    mocks.fetchOverview.mockResolvedValue({
      subjects: { total: 3, active: 2, suspended: 1 },
      firms: { total: 2, active: 2, suspended: 0 },
      companies: { total: 4, active: 3, suspended: 1, archived: 0 },
      platform_roles: 1,
      bootstrap_claimed: true,
    });
    mocks.fetchIdentities.mockResolvedValue([{
      subject_id: '22222222-2222-4222-8222-222222222222',
      display_name: 'Operadora UAT', status: 'active',
      created_at: '2026-08-30T12:00:00Z', active_firms: 1,
      platform_roles: ['platform_operator'],
    }]);
    mocks.fetchOrganizations.mockResolvedValue([{
      firm_id: '33333333-3333-4333-8333-333333333333',
      legal_name: 'Firma UAT', status: 'active',
      created_at: '2026-08-30T12:00:00Z', active_members: 2,
    }]);
    mocks.fetchDiagnostics.mockResolvedValue({
      environment: 'test', release_id: 'fnc-uat-candidate', revision: 'a'.repeat(40),
      services: [{ name: 'postgresql', status: 'up', detail: 'PostgreSQL 17' }],
      capabilities: {
        real_data: false, managed_identity: true, ai_gateway: false,
        payments: false, break_glass: false,
      },
    });
    mocks.fetchAudit.mockResolvedValue([]);
  });

  it('presenta control operativo sin convertirlo en acceso financiero', async () => {
    render(await PlatformPage());

    expect(screen.getByRole('heading', {
      level: 1, name: 'Administración de Fincilia',
    })).toBeInTheDocument();
    expect(screen.getByText('Firma UAT')).toBeInTheDocument();
    expect(screen.getByText('PostgreSQL 17')).toBeInTheDocument();
    expect(screen.getByText(/Break-glass:/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Asignar' })).toBeInTheDocument();
    expect(screen.queryByText(/monto|saldo bancario|tax id/i)).not.toBeInTheDocument();
  });

  it('redirige una denegación server-side sin confiar en la navegación', async () => {
    mocks.fetchOverview.mockRejectedValue(new mocks.ApiError(403, 'forbidden'));
    await expect(PlatformPage()).rejects.toThrow('NEXT_REDIRECT');
    expect(mocks.redirect).toHaveBeenCalledWith('/empresas');
  });
});

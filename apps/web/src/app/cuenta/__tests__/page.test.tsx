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
    fetchMe: vi.fn(),
    readSession: vi.fn(),
    redirect: vi.fn((): never => { throw new Error('NEXT_REDIRECT'); }),
  };
});

vi.mock('next/navigation', () => ({ redirect: mocks.redirect }));
vi.mock('@/lib/session', () => ({ readSession: mocks.readSession }));
vi.mock('@/lib/api', () => ({ ApiError: mocks.ApiError, fetchMe: mocks.fetchMe }));
vi.mock('@/app/empresas/sign-out', () => ({ SignOut: () => <button>Salir</button> }));

import AccountPage from '../page';

describe('AccountPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.readSession.mockResolvedValue({ token: 'synthetic-token', displayName: 'Ada' });
    mocks.fetchMe.mockResolvedValue({
      subject_id: '11111111-1111-4111-8111-111111111111',
      display_name: 'Ada Sintética',
      identity_mode: 'local_synthetic',
      credential_management: 'synthetic_demo_only',
      session_issued_at: 1_787_900_000,
      session_expires_at: 1_787_903_600,
      companies: [{
        company_id: '22222222-2222-4222-8222-222222222222',
        legal_name: 'Empresa Sintética',
        country_code: 'CO',
        status: 'active',
        roles: ['owner', 'preparer'],
      }],
    });
  });

  it('explica el modo sintetico y enlaza solo alcances devueltos por la API', async () => {
    render(await AccountPage());

    expect(screen.getByRole('heading', { level: 1, name: 'Tu cuenta' })).toBeInTheDocument();
    expect(screen.getByText('Cuenta local de demostración')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Abrir empresa' })).toHaveAttribute(
      'href', '/empresas/22222222-2222-4222-8222-222222222222',
    );
    expect(screen.getByRole('link', { name: 'Gestionar equipo' })).toBeInTheDocument();
    expect(screen.queryByText(/@demo\.local/)).not.toBeInTheDocument();
  });

  it('presenta Google como identidad administrada sin afirmar permisos', async () => {
    mocks.fetchMe.mockResolvedValue({
      ...(await mocks.fetchMe()),
      identity_mode: 'managed_oidc',
      credential_management: 'external_identity_provider',
    });

    render(await AccountPage());

    expect(screen.getByText('Google mediante Cognito')).toBeInTheDocument();
    expect(screen.getByText(/Fincilia resuelve empresas y roles/)).toBeInTheDocument();
  });
});

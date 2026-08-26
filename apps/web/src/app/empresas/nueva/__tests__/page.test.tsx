import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  fetchManageableFirms: vi.fn(),
  readSession: vi.fn(),
  redirect: vi.fn((): never => {
    throw new Error('NEXT_REDIRECT');
  }),
}));

vi.mock('next/navigation', () => ({ redirect: mocks.redirect }));
vi.mock('@/lib/session', () => ({ readSession: mocks.readSession }));
vi.mock('@/lib/api', () => ({
  ApiError: class ApiError extends Error {
    constructor(readonly status: number, message: string) {
      super(message);
    }
  },
  fetchManageableFirms: mocks.fetchManageableFirms,
}));
vi.mock('../company-form', () => ({
  CompanyForm: ({ firms }: { firms: Array<{ legal_name: string }> }) => (
    <div data-testid="company-form">{firms.map((firm) => firm.legal_name).join(',')}</div>
  ),
}));

import NewCompanyPage from '../page';

describe('NewCompanyPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.readSession.mockResolvedValue({ token: 'token-sintetico' });
  });

  it('entrega al formulario solo las firmas autorizadas por la API', async () => {
    mocks.fetchManageableFirms.mockResolvedValue([{
      firm_id: '5f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5e',
      legal_name: 'Firma Sintetica',
      firm_role: 'owner',
    }]);

    render(await NewCompanyPage());

    expect(screen.getByRole('heading', { level: 1, name: 'Nueva empresa' }))
      .toBeInTheDocument();
    expect(screen.getByTestId('company-form')).toHaveTextContent('Firma Sintetica');
  });

  it('no renderiza campos de alta cuando el servidor no concede una firma', async () => {
    mocks.fetchManageableFirms.mockResolvedValue([]);

    render(await NewCompanyPage());

    expect(screen.getByRole('heading', { level: 2, name: 'No puedes crear empresas' }))
      .toBeInTheDocument();
    expect(screen.queryByTestId('company-form')).not.toBeInTheDocument();
  });

  it('redirige una visita sin sesion antes de consultar firmas', async () => {
    mocks.readSession.mockResolvedValue(null);

    await expect(NewCompanyPage()).rejects.toThrow('NEXT_REDIRECT');
    expect(mocks.fetchManageableFirms).not.toHaveBeenCalled();
  });
});

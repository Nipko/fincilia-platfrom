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
    loadPortfolioSnapshots: vi.fn(),
    readSession: vi.fn(),
    redirect: vi.fn((): never => {
      throw new Error('NEXT_REDIRECT');
    }),
  };
});

vi.mock('next/navigation', () => ({ redirect: mocks.redirect }));
vi.mock('@/lib/session', () => ({ readSession: mocks.readSession }));
vi.mock('@/lib/api', () => ({
  ApiError: mocks.ApiError,
  fetchMe: mocks.fetchMe,
}));
vi.mock('@/lib/portfolio', () => ({
  loadPortfolioSnapshots: mocks.loadPortfolioSnapshots,
}));

import CompaniesPage from '../page';

const company = {
  company_id: 'company-synthetic-a',
  legal_name: 'Empresa Sintetica A',
  country_code: 'CO',
  status: 'active',
  roles: ['accountant'],
};

describe('CompaniesPage portfolio', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.readSession.mockResolvedValue({
      token: 'token-synthetic',
      displayName: 'Ada',
    });
    mocks.fetchMe.mockResolvedValue({
      display_name: 'Ada',
      companies: [company],
    });
  });

  it('distingue falta de acceso de un conteo cero', async () => {
    mocks.loadPortfolioSnapshots.mockResolvedValue([
      {
        company,
        access: 'available',
        documents: { state: 'restricted' },
        datasets: { state: 'restricted' },
        expectations: { state: 'restricted' },
      },
    ]);

    render(await CompaniesPage());

    expect(screen.getAllByText('Sin acceso para este rol')).toHaveLength(3);
    expect(screen.queryByText(/0 total/)).not.toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: 'Abrir Empresa Sintetica A' }),
    ).toHaveAttribute('href', '/empresas/company-synthetic-a');
  });

  it('presenta conteos como carga operativa y no como saldos', async () => {
    mocks.loadPortfolioSnapshots.mockResolvedValue([
      {
        company,
        access: 'available',
        documents: { state: 'available', value: { visible: 8, quarantine: 2 } },
        datasets: {
          state: 'available',
          value: { visible: 4, pendingReview: 2, partial: 1, published: 1 },
        },
        expectations: {
          state: 'available',
          value: { overdue: 3, dueSoon: 1, pending: 5 },
        },
      },
    ]);

    render(await CompaniesPage());

    expect(screen.getByText('8 en ventana · 2 en cuarentena')).toBeInTheDocument();
    expect(screen.getByText('2 por revisar · 1 parciales')).toBeInTheDocument();
    expect(screen.getByText('3 vencidos · 1 proximos')).toBeInTheDocument();
    expect(screen.getByText(/no saldos/i)).toBeInTheDocument();
  });
});

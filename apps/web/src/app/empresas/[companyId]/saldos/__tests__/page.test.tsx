import { render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('server-only', () => ({}));

const mocks = vi.hoisted(() => ({
  fetchAccountBalances: vi.fn(),
  fetchBalanceEvidence: vi.fn(),
  fetchCompany: vi.fn(),
  readSession: vi.fn(),
  redirect: vi.fn((): never => { throw new Error('NEXT_REDIRECT'); }),
  notFound: vi.fn((): never => { throw new Error('NEXT_NOT_FOUND'); }),
}));

vi.mock('next/navigation', () => ({
  redirect: mocks.redirect,
  notFound: mocks.notFound,
}));
vi.mock('@/lib/session', () => ({ readSession: mocks.readSession }));
vi.mock('@/app/actions', () => ({ observeBalanceAction: vi.fn() }));
vi.mock('@/lib/api', () => ({
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
  fetchAccountBalances: mocks.fetchAccountBalances,
  fetchBalanceEvidence: mocks.fetchBalanceEvidence,
  fetchCompany: mocks.fetchCompany,
}));

import BalancesPage from '../page';

const COMPANY = '161b0037-c445-50aa-b400-72632d3f53f0';

describe('BalancesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.readSession.mockResolvedValue({ token: 'synthetic-token' });
    mocks.fetchCompany.mockResolvedValue({
      legal_name: 'Panaderia La Espiga SAS',
      permissions: ['movement.read', 'close.prepare'],
    });
    mocks.fetchBalanceEvidence.mockResolvedValue({
      limit: 20,
      truncated: false,
      items: [{
        source_record_id: '61111111-1111-4111-8111-111111111111',
        dataset_version_id: '62222222-2222-4222-8222-222222222222',
        source_name: 'Extracto sintetico',
        financial_account_id: '63333333-3333-4333-8333-333333333333',
        account_name: 'Cuenta corriente demo',
        currency_code: 'COP',
        record_ordinal: 7,
        source_timezone: 'America/Bogota',
        fields: [
          { index: 0, label: 'occurred_on', value: '31/07/2026' },
          { index: 1, label: 'description', value: 'Saldo final sintetico' },
          { index: 2, label: 'amount', value: '-1.234,56' },
        ],
      }],
    });
    mocks.fetchAccountBalances.mockResolvedValue({
      limit: 100,
      truncated: false,
      notice: 'observations_only',
      items: [{
        balance_id: '64444444-4444-4444-8444-444444444444',
        financial_account_id: '63333333-3333-4333-8333-333333333333',
        account_name: 'Cuenta corriente demo',
        source_record_id: '61111111-1111-4111-8111-111111111111',
        source_name: 'Extracto sintetico',
        record_ordinal: 7,
        balance_type: 'closing',
        amount: '-1234.560000000000',
        currency_code: 'COP',
        as_of: '2026-08-01T04:59:59.999999+00:00',
        source_timezone: 'America/Bogota',
        amount_field_index: 2,
        as_of_field_index: 0,
        lineage_state: 'required_pending',
        created_at: '2026-08-25T12:00:00+00:00',
        replayed: false,
        proves_completeness: false,
        proves_reconciliation: false,
      }],
    });
  });

  it('muestra seleccion de celdas e historico sin afirmar cierre', async () => {
    render(await BalancesPage({ params: Promise.resolve({ companyId: COMPANY }) }));

    expect(screen.getByRole('heading', { name: 'Saldos por cuenta' })).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'Fila de evidencia' })).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'Columna del importe' }))
      .toHaveValue('2');
    expect(screen.getByRole('combobox', { name: 'Columna de la fecha del saldo' }))
      .toHaveValue('0');
    const history = screen.getByRole('table');
    expect(within(history).getByText('-1234.56')).toBeInTheDocument();
    expect(within(history).getByText('Pendiente')).toBeInTheDocument();
    expect(screen.getByText(/aun no son entrada de cierre/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /cerrar/i })).not.toBeInTheDocument();
  });

  it('un rol lector ve historico pero no consulta valores candidatos', async () => {
    mocks.fetchCompany.mockResolvedValue({
      legal_name: 'Panaderia La Espiga SAS',
      permissions: ['movement.read'],
    });

    render(await BalancesPage({ params: Promise.resolve({ companyId: COMPANY }) }));

    expect(screen.getByText(/puedes consultar el historico/i)).toBeInTheDocument();
    expect(mocks.fetchBalanceEvidence).not.toHaveBeenCalled();
    expect(screen.queryByRole('combobox', { name: 'Fila de evidencia' }))
      .not.toBeInTheDocument();
  });

  it('una lista vacia no se presenta como saldo cero', async () => {
    mocks.fetchAccountBalances.mockResolvedValue({
      limit: 100, truncated: false, notice: 'observations_only', items: [],
    });

    render(await BalancesPage({ params: Promise.resolve({ companyId: COMPANY }) }));

    expect(screen.getByText(/lista vacia no significa saldo cero/i)).toBeInTheDocument();
  });
});

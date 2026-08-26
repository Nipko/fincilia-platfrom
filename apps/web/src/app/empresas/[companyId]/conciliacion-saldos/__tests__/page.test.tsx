import { render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('server-only', () => ({}));

const mocks = vi.hoisted(() => ({
  fetchAccountBalances: vi.fn(), fetchBalanceEvidence: vi.fn(),
  fetchBalanceReconciliation: vi.fn(), fetchCompany: vi.fn(), readSession: vi.fn(),
  redirect: vi.fn((): never => { throw new Error('NEXT_REDIRECT'); }),
  notFound: vi.fn((): never => { throw new Error('NEXT_NOT_FOUND'); }),
}));

vi.mock('next/navigation', () => ({ redirect: mocks.redirect, notFound: mocks.notFound }));
vi.mock('@/lib/session', () => ({ readSession: mocks.readSession }));
vi.mock('@/app/actions', () => ({
  assessCompletenessAction: vi.fn(), decideReconcilingItemAction: vi.fn(),
  evaluateBalanceReconciliationAction: vi.fn(), proposeReconcilingItemAction: vi.fn(),
}));
vi.mock('@/lib/api', () => ({
  ApiError: class ApiError extends Error { status: number; constructor(status: number) {
    super(); this.status = status;
  } },
  fetchAccountBalances: mocks.fetchAccountBalances,
  fetchBalanceEvidence: mocks.fetchBalanceEvidence,
  fetchBalanceReconciliation: mocks.fetchBalanceReconciliation,
  fetchCompany: mocks.fetchCompany,
}));

import BalanceReconciliationPage from '../page';

const COMPANY = '161b0037-c445-50aa-b400-72632d3f53f0';
const ASSESSMENT = '21111111-1111-4111-8111-111111111111';
const ROOT = '22222222-2222-4222-8222-222222222222';

describe('BalanceReconciliationPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.readSession.mockResolvedValue({ token: 'synthetic-token' });
    mocks.fetchCompany.mockResolvedValue({
      legal_name: 'Panaderia La Espiga SAS',
      permissions: ['movement.read', 'close.prepare', 'close.approve'],
    });
    mocks.fetchBalanceEvidence.mockResolvedValue({
      limit: 50, truncated: false, items: [{
        source_record_id: '31111111-1111-4111-8111-111111111111',
        dataset_version_id: '32222222-2222-4222-8222-222222222222',
        source_name: 'Extracto sintetico', financial_account_id: 'account',
        account_name: 'Cuenta corriente demo', currency_code: 'COP',
        record_ordinal: 7, source_timezone: 'America/Bogota', fields: [],
      }],
    });
    mocks.fetchAccountBalances.mockResolvedValue({
      limit: 100, truncated: false, notice: 'observations_only', items: [{
        balance_id: '41111111-1111-4111-8111-111111111111', balance_type: 'closing',
        financial_account_id: 'account', source_timezone: 'America/Bogota',
        account_name: 'Cuenta corriente demo', amount: '1000.000000000000',
        currency_code: 'COP', as_of: '2026-03-31T23:59:59Z',
      }, {
        balance_id: '42222222-2222-4222-8222-222222222222', balance_type: 'ledger',
        financial_account_id: 'account', source_timezone: 'America/Bogota',
        account_name: 'Cuenta corriente demo', amount: '1100.000000000000',
        currency_code: 'COP', as_of: '2026-03-31T23:59:59Z',
      }],
    });
    mocks.fetchBalanceReconciliation.mockResolvedValue({
      limit: 50, truncated: false,
      totals: { expectations: 1, assessments: 1, statements: 1, items: 1 },
      notice: 'diagnostic_only', expectations: [{
        expectation_id: '51111111-1111-4111-8111-111111111111',
        data_source_id: 'source', source_name: 'Banco sintetico',
        financial_account_id: 'account', account_name: 'Cuenta corriente demo',
        period_start: '2026-03-01', period_end: '2026-03-31', state: 'satisfied',
        has_artifact: true, assessed: true,
      }], assessments: [{
        assessment_id: ASSESSMENT, data_source_id: 'source',
        source_name: 'Banco sintetico', source_expectation_id: 'expectation',
        financial_account_id: 'account', account_name: 'Cuenta corriente demo',
        dataset_version_id: 'dataset', period_start: '2026-03-01',
        period_end: '2026-03-31', state: 'verified', lineage_state: 'complete',
        created_at: '2026-04-01T00:00:00Z', replayed: false, controls: [{
          control_result_id: 'control', assessment_id: ASSESSMENT,
          control_type: 'provenance_integrity', required: true, outcome: 'match',
          expected_value: { value: true }, observed_value: { value: true },
          value_type: 'boolean', reason: null, lineage_state: 'complete',
        }],
      }], statements: [{
        statement_id: '61111111-1111-4111-8111-111111111111', statement_root_id: ROOT,
        version: 2, financial_account_id: 'account', account_name: 'Cuenta corriente demo',
        period_start: '2026-03-01', period_end: '2026-03-31', currency_code: 'COP',
        bank_closing_balance_id: 'bank', books_closing_balance_id: 'books',
        completeness_assessment_ids: [ASSESSMENT], confirmed_reconciling_item_ids: ['item'],
        bank_closing_balance: '1000.000000000000', books_closing_balance: '1100.000000000000',
        confirmed_additions_to_bank: '100.000000000000',
        confirmed_deductions_from_bank: '0.000000000000',
        adjusted_bank_balance: '1100.000000000000', unexplained_difference: '0.000000000000',
        state: 'balanced', lineage_state: 'required_pending',
        created_at: '2026-04-01T00:00:00Z', replayed: false, certifies_close: false,
      }], items: [{
        item_decision_id: 'item-decision', item_root_id: 'item-root', statement_root_id: ROOT,
        adjustment_side: 'add_to_bank', amount: '100.000000000000',
        currency_code: 'COP', reason_code: 'documented_timing', state: 'confirmed',
        prepared_by: 'ana', approved_by: 'beto', decision_version: 2,
        lineage_state: 'complete', created_at: '2026-04-01T00:00:00Z',
      }],
    });
  });

  it('hace visible la ecuacion y nunca afirma cierre certificado', async () => {
    render(await BalanceReconciliationPage({ params: Promise.resolve({ companyId: COMPANY }) }));
    expect(screen.getByRole('heading', { name: 'Conciliacion de saldos' })).toBeInTheDocument();
    const equation = screen.getByLabelText('Ecuacion version 2');
    expect(within(equation).getByText('Banco ajustado')).toBeInTheDocument();
    expect(within(equation).getAllByText('1100')).toHaveLength(2);
    expect(screen.getAllByText('Diferencia explicada').length).toBeGreaterThan(0);
    expect(screen.getByText(/no es un cierre certificado/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /cerrar|certificar/i })).not.toBeInTheDocument();
  });

  it('expone fuente, controles, evidencia y revision independiente', async () => {
    render(await BalanceReconciliationPage({ params: Promise.resolve({ companyId: COMPANY }) }));
    expect(screen.getByText('Integridad de evidencia')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reevaluar evidencia' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Calcular nueva version' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Proponer partida' })).toBeEnabled();
  });

  it('un lector no recibe valores de evidencia ni acciones financieras', async () => {
    mocks.fetchCompany.mockResolvedValue({
      legal_name: 'Panaderia La Espiga SAS', permissions: ['movement.read'],
    });
    render(await BalanceReconciliationPage({ params: Promise.resolve({ companyId: COMPANY }) }));
    expect(mocks.fetchBalanceEvidence).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: 'Calcular nueva version' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Proponer partida' })).not.toBeInTheDocument();
  });
});

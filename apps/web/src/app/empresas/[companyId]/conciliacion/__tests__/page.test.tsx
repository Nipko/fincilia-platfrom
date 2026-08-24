import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  fetchCompany: vi.fn(),
  fetchDatasets: vi.fn(),
  fetchCandidates: vi.fn(),
  readSession: vi.fn(),
  redirect: vi.fn(),
}));

vi.mock('next/navigation', () => ({ redirect: mocks.redirect }));
vi.mock('@/lib/session', () => ({ readSession: mocks.readSession }));
vi.mock('@/lib/api', () => ({
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
  fetchCompany: mocks.fetchCompany,
  fetchDatasets: mocks.fetchDatasets,
  fetchReconciliationCandidates: mocks.fetchCandidates,
}));

import ReconciliationPage from '../page';

const COMPANY = '161b0037-c445-50aa-b400-72632d3f53f0';
const LEFT = '11111111-1111-4111-8111-111111111111';
const RIGHT = '22222222-2222-4222-8222-222222222222';

function dataset(id: string) {
  return {
    dataset_version_id: id,
    artifact_id: crypto.randomUUID(),
    state: 'validated',
    movement_count: 2,
    rejected_count: 0,
    prepared_at: '2026-08-24T12:00:00+00:00',
    published_at: null,
  };
}

describe('ReconciliationPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.readSession.mockResolvedValue({ token: 'synthetic-token' });
    mocks.fetchCompany.mockResolvedValue({
      legal_name: 'Servicios Espiga SAS',
      permissions: ['movement.read'],
    });
    mocks.fetchDatasets.mockResolvedValue([dataset(LEFT), dataset(RIGHT)]);
  });

  it('presenta pares explicados sin controles de decision financiera', async () => {
    mocks.fetchCandidates.mockResolvedValue({
      mode: 'candidate_only',
      proves_balance_reconciliation: false,
      rules: ['exact_amount'],
      reference_role: 'explanatory_order_only',
      max_days: 3,
      offset: 0,
      limit: 25,
      truncated: false,
      left_dataset: { dataset_version_id: LEFT },
      right_dataset: { dataset_version_id: RIGHT },
      candidates: [{
        left: {
          movement_id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
          amount: '1234.560000000000', currency: 'COP', direction: 'outflow',
          description: 'Pago sintetico', reference: 'REF-01',
          occurred_on: '2026-02-13', state: 'proposed', record_ordinal: 2,
        },
        right: {
          movement_id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
          amount: '1234.560000000000', currency: 'COP', direction: 'inflow',
          description: 'Abono sintetico', reference: 'REF-01',
          occurred_on: '2026-02-14', state: 'proposed', record_ordinal: 4,
        },
        date_distance_days: 1,
        signals: ['exact_amount', 'same_currency', 'opposite_direction',
          'different_financial_account', 'date_within_explicit_window',
          'same_normalised_reference'],
      }],
    });

    render(await ReconciliationPage({
      params: Promise.resolve({ companyId: COMPANY }),
      searchParams: Promise.resolve({
        izquierda: LEFT, derecha: RIGHT, ventana: '3', pagina: '0',
      }),
    }));

    expect(screen.getByRole('heading', { name: 'Conciliacion visual' }))
      .toBeInTheDocument();
    expect(screen.getByText('Solo candidatos.')).toBeInTheDocument();
    expect(screen.getAllByText('1.234,56 COP')).toHaveLength(2);
    expect(screen.getByText('misma referencia normalizada')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Ver evidencia izquierda' }))
      .toHaveAttribute('href', expect.stringContaining('/movimientos/aaaaaaaa'));
    expect(screen.getByRole('link', { name: 'Ver evidencia derecha' }))
      .toHaveAttribute('href', expect.stringContaining('/movimientos/bbbbbbbb'));
    expect(screen.queryByRole('button', { name: /confirmar|aprobar|automatic/i }))
      .not.toBeInTheDocument();
  });

  it('distingue cero candidatos de una conciliacion exitosa', async () => {
    mocks.fetchCandidates.mockResolvedValue({
      candidates: [], truncated: false, mode: 'candidate_only',
      proves_balance_reconciliation: false,
    });
    render(await ReconciliationPage({
      params: Promise.resolve({ companyId: COMPANY }),
      searchParams: Promise.resolve({ izquierda: LEFT, derecha: RIGHT }),
    }));
    expect(screen.getByText('No hay candidatos con estas reglas')).toBeInTheDocument();
    expect(screen.getByText(/Esto no demuestra que falten movimientos/))
      .toBeInTheDocument();
  });
});

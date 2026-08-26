import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  fetchCompany: vi.fn(),
  fetchDatasets: vi.fn(),
  fetchCandidates: vi.fn(),
  fetchGroups: vi.fn(),
  fetchMovements: vi.fn(),
  fetchReviews: vi.fn(),
  readSession: vi.fn(),
  redirect: vi.fn(),
}));

vi.mock('next/navigation', () => ({ redirect: mocks.redirect }));
vi.mock('@/lib/session', () => ({ readSession: mocks.readSession }));
vi.mock('@/app/actions', () => ({
  proposeMatchAction: vi.fn(),
  proposeMatchGroupAction: vi.fn(),
  decideMatchAction: vi.fn(),
}));
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
  fetchReconciliationGroups: mocks.fetchGroups,
  fetchMovements: mocks.fetchMovements,
  fetchReconciliationReviews: mocks.fetchReviews,
}));

import ReconciliationPage from '../page';

const COMPANY = '161b0037-c445-50aa-b400-72632d3f53f0';
const LEFT = '11111111-1111-4111-8111-111111111111';
const RIGHT = '22222222-2222-4222-8222-222222222222';
const LEFT_MOVEMENT = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const RIGHT_MOVEMENT = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';

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
    mocks.fetchGroups.mockResolvedValue([]);
    mocks.fetchMovements.mockResolvedValue([]);
    mocks.fetchReviews.mockResolvedValue([]);
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

  it('ofrece proponer solo cuando la API concedio match.propose', async () => {
    mocks.fetchCompany.mockResolvedValue({
      legal_name: 'Servicios Espiga SAS',
      permissions: ['movement.read', 'match.propose', 'match.reject'],
    });
    mocks.fetchCandidates.mockResolvedValue({
      candidates: [{
        left: {
          movement_id: LEFT_MOVEMENT, amount: '10.000000000000', currency: 'COP',
          direction: 'outflow', description: 'Pago', reference: null,
          occurred_on: '2026-02-13', state: 'proposed', record_ordinal: 2,
        },
        right: {
          movement_id: RIGHT_MOVEMENT, amount: '10.000000000000', currency: 'COP',
          direction: 'inflow', description: 'Abono', reference: null,
          occurred_on: '2026-02-14', state: 'proposed', record_ordinal: 2,
        },
        date_distance_days: 1,
        signals: ['exact_amount'],
      }],
      truncated: false,
      mode: 'candidate_only',
      proves_balance_reconciliation: false,
    });

    render(await ReconciliationPage({
      params: Promise.resolve({ companyId: COMPANY }),
      searchParams: Promise.resolve({ izquierda: LEFT, derecha: RIGHT }),
    }));

    expect(screen.getByRole('button', { name: 'Enviar a revision humana' }))
      .toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Confirmar revision' }))
      .not.toBeInTheDocument();
  });

  it('muestra decision pendiente y controles concedidos sin decidir SoD en web', async () => {
    mocks.fetchCompany.mockResolvedValue({
      legal_name: 'Servicios Espiga SAS',
      permissions: ['movement.read', 'match.confirm', 'match.reject'],
    });
    mocks.fetchCandidates.mockResolvedValue({
      candidates: [{
        left: {
          movement_id: LEFT_MOVEMENT, amount: '10.000000000000', currency: 'COP',
          direction: 'outflow', description: 'Pago', reference: null,
          occurred_on: '2026-02-13', state: 'proposed', record_ordinal: 2,
        },
        right: {
          movement_id: RIGHT_MOVEMENT, amount: '10.000000000000', currency: 'COP',
          direction: 'inflow', description: 'Abono', reference: null,
          occurred_on: '2026-02-14', state: 'proposed', record_ordinal: 2,
        },
        date_distance_days: 1,
        signals: ['exact_amount'],
      }],
      truncated: false,
      mode: 'candidate_only',
      proves_balance_reconciliation: false,
    });
    mocks.fetchReviews.mockResolvedValue([{
      candidate_id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
      left_movement_id: LEFT_MOVEMENT,
      right_movement_id: RIGHT_MOVEMENT,
      confirmation_conflict: false,
      proposed_by_name: 'Ana Preparadora',
      proposed_at: '2026-08-24T12:00:00+00:00',
      status: 'open',
      decision: null,
      financial_effect: 'none',
      proves_balance_reconciliation: false,
    }]);

    render(await ReconciliationPage({
      params: Promise.resolve({ companyId: COMPANY }),
      searchParams: Promise.resolve({ izquierda: LEFT, derecha: RIGHT }),
    }));

    expect(screen.getByText('Pendiente de decision humana')).toBeInTheDocument();
    expect(screen.getByText(/2026-08-24 12:00 UTC/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Confirmar revision' }))
      .toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Rechazar candidato' }))
      .toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Enviar a revision humana' }))
      .not.toBeInTheDocument();
  });

  it('presenta composicion 1:N y N:1 e historial sin boton de confirmar', async () => {
    mocks.fetchCompany.mockResolvedValue({
      legal_name: 'Servicios Espiga SAS',
      permissions: ['movement.read', 'match.propose'],
    });
    mocks.fetchCandidates.mockResolvedValue({
      candidates: [], truncated: false, mode: 'candidate_only',
      proves_balance_reconciliation: false,
    });
    const leftMovements = [
      { movement_id: LEFT_MOVEMENT, amount: '300.000000000000', currency: 'COP',
        direction: 'outflow', description: 'Pago total', reference: null,
        occurred_on: '2026-02-13', state: 'proposed', record_ordinal: 2 },
      { movement_id: crypto.randomUUID(), amount: '25.000000000000', currency: 'COP',
        direction: 'outflow', description: 'Otro pago', reference: null,
        occurred_on: '2026-02-14', state: 'proposed', record_ordinal: 3 },
    ];
    const related = [
      { movement_id: RIGHT_MOVEMENT, amount: '100.000000000000', currency: 'COP',
        direction: 'inflow', description: 'Abono uno', reference: null,
        occurred_on: '2026-02-14', state: 'proposed', record_ordinal: 4 },
      { movement_id: crypto.randomUUID(), amount: '200.000000000000', currency: 'COP',
        direction: 'inflow', description: 'Abono dos', reference: null,
        occurred_on: '2026-02-15', state: 'proposed', record_ordinal: 5 },
    ];
    mocks.fetchMovements.mockImplementation(
      async (_token: string, _company: string, datasetId: string) => (
        datasetId === LEFT ? leftMovements : related));
    mocks.fetchGroups.mockResolvedValue([{
      group_candidate_id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
      anchor_dataset_id: LEFT,
      related_dataset_id: RIGHT,
      anchor: leftMovements[0],
      related,
      related_movement_count: 2,
      related_total: '300.000000000000',
      difference: '0.000000000000',
      currency: 'COP',
      rule_version: 'fnc-rec-group-whole-v1',
      proposed_by: crypto.randomUUID(),
      proposed_by_name: 'Ana Preparadora',
      proposed_at: '2026-08-26T12:00:00+00:00',
      view_relation: 'one_to_many',
      status: 'draft',
      financial_effect: 'none',
      proves_balance_reconciliation: false,
      can_confirm: false,
    }]);

    render(await ReconciliationPage({
      params: Promise.resolve({ companyId: COMPANY }),
      searchParams: Promise.resolve({ izquierda: LEFT, derecha: RIGHT }),
    }));

    expect(screen.getByRole('heading', { name: 'Propuestas agrupadas 1:N y N:1' }))
      .toBeInTheDocument();
    expect(screen.getByRole('form', { name: 'Crear propuesta 1:N' }))
      .toBeInTheDocument();
    expect(screen.getByRole('form', { name: 'Crear propuesta N:1' }))
      .toBeInTheDocument();
    expect(screen.getAllByText('300 COP').length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(/Estado draft: no hay asignaciones/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /confirmar grupo/i }))
      .not.toBeInTheDocument();
  });

  it('bloquea confirmar un movimiento ya reservado y conserva el rechazo', async () => {
    mocks.fetchCompany.mockResolvedValue({
      legal_name: 'Servicios Espiga SAS',
      permissions: ['movement.read', 'match.confirm', 'match.reject'],
    });
    mocks.fetchCandidates.mockResolvedValue({
      candidates: [{
        left: {
          movement_id: LEFT_MOVEMENT, amount: '10.000000000000', currency: 'COP',
          direction: 'outflow', description: 'Pago', reference: null,
          occurred_on: '2026-02-13', state: 'proposed', record_ordinal: 2,
        },
        right: {
          movement_id: RIGHT_MOVEMENT, amount: '10.000000000000', currency: 'COP',
          direction: 'inflow', description: 'Abono', reference: null,
          occurred_on: '2026-02-14', state: 'proposed', record_ordinal: 2,
        },
        date_distance_days: 1,
        signals: ['exact_amount'],
      }],
      truncated: false,
      mode: 'candidate_only',
      proves_balance_reconciliation: false,
    });
    mocks.fetchReviews.mockResolvedValue([{
      candidate_id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
      left_movement_id: LEFT_MOVEMENT,
      right_movement_id: RIGHT_MOVEMENT,
      proposed_by_name: 'Ana Preparadora',
      proposed_at: '2026-08-24T12:00:00+00:00',
      status: 'open',
      decision: null,
      confirmation_conflict: true,
      financial_effect: 'none',
      proves_balance_reconciliation: false,
    }]);

    render(await ReconciliationPage({
      params: Promise.resolve({ companyId: COMPANY }),
      searchParams: Promise.resolve({ izquierda: LEFT, derecha: RIGHT }),
    }));

    expect(screen.getByText('No se puede confirmar este par')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Confirmar revision' }))
      .not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Rechazar candidato' }))
      .toBeInTheDocument();
  });

  it('prioriza una URL invalida aunque aun no existan dos datasets aptos', async () => {
    mocks.fetchDatasets.mockResolvedValue([dataset(LEFT)]);

    render(await ReconciliationPage({
      params: Promise.resolve({ companyId: COMPANY }),
      searchParams: Promise.resolve({
        izquierda: 'repetido', derecha: 'repetido', ventana: '32',
      }),
    }));

    expect(screen.getByText('La comparacion solicitada no es valida'))
      .toBeInTheDocument();
    expect(screen.queryByText('Se necesitan dos datasets aptos'))
      .not.toBeInTheDocument();
    expect(mocks.fetchCandidates).not.toHaveBeenCalled();
  });
});

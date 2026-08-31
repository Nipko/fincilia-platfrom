import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('server-only', () => ({}));

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
    loadReviewInbox: vi.fn(),
    readSession: vi.fn(),
    redirect: vi.fn((): never => { throw new Error('NEXT_REDIRECT'); }),
  };
});

vi.mock('next/navigation', () => ({ redirect: mocks.redirect }));
vi.mock('@/lib/session', () => ({ readSession: mocks.readSession }));
vi.mock('@/lib/api', () => ({ ApiError: mocks.ApiError, fetchMe: mocks.fetchMe }));
vi.mock('@/lib/review-inbox', () => ({
  loadReviewInbox: mocks.loadReviewInbox,
  parseReviewFilter: (value: unknown) => value === 'todas' ? 'todas' : 'abiertas',
  sortedReviewEntries: (snapshots: Array<{ company: unknown; items: unknown[] }>) =>
    snapshots.flatMap((snapshot) => snapshot.items.map((review) => ({
      company: snapshot.company,
      review,
    }))),
  formatReviewTimestamp: (value: string) =>
    `${new Date(value).toISOString().slice(0, 16).replace('T', ' ')} UTC`,
}));

import ReviewsPage from '../page';

const company = {
  company_id: 'company-synthetic-a',
  legal_name: 'Empresa Sintetica A',
  country_code: 'CO',
  status: 'active',
  roles: ['reviewer'],
};

const item = {
  candidate_id: 'candidate-synthetic-a',
  left_movement_id: 'movement-left',
  right_movement_id: 'movement-right',
  left_dataset_id: 'dataset-left',
  right_dataset_id: 'dataset-right',
  rule_version: 'fnc-rec-exact-v1',
  signals: ['exact_amount', 'same_currency'],
  date_window_days: 3,
  date_distance_days: 1,
  proposed_by: 'subject-ada',
  proposed_by_name: 'Ada Preparadora',
  proposed_at: '2026-08-24T12:00:00Z',
  status: 'open',
  decision: null,
  financial_effect: 'none',
  proves_balance_reconciliation: false,
};

describe('ReviewsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.readSession.mockResolvedValue({ token: 'token-synthetic' });
    mocks.fetchMe.mockResolvedValue({ display_name: 'Beto Revisor', companies: [company] });
  });

  it('muestra trabajo trazable y enlaza el expediente exacto', async () => {
    mocks.loadReviewInbox.mockResolvedValue([
      { company, access: 'available', truncated: false, items: [item] },
    ]);
    render(await ReviewsPage({ searchParams: Promise.resolve({ estado: 'abiertas' }) }));

    expect(screen.getByRole('heading', { name: 'Bandeja de revisiones' }))
      .toBeInTheDocument();
    expect(screen.getByText('Empresa Sintetica A')).toBeInTheDocument();
    expect(screen.getByText('Ada Preparadora')).toBeInTheDocument();
    expect(screen.getByText(/sin efecto financiero/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Abrir expediente' })).toHaveAttribute(
      'href',
      '/empresas/company-synthetic-a/conciliacion?' +
        'izquierda=dataset-left&derecha=dataset-right&ventana=3&referencia=all&pagina=0&' +
        'revision=candidate-synthetic-a' +
        '#revision-candidate-synthetic-a',
    );
  });

  it('declara vista parcial en vez de convertir una empresa fallida en cero', async () => {
    mocks.loadReviewInbox.mockResolvedValue([
      { company, access: 'unavailable', truncated: false, items: [] },
    ]);
    render(await ReviewsPage({ searchParams: Promise.resolve({ estado: 'abiertas' }) }));

    expect(screen.getByText('Vista parcial.')).toBeInTheDocument();
    expect(screen.getByText(/no se presentan como cero revisiones/i)).toBeInTheDocument();
    expect(screen.getByText(/no certifica que las empresas esten conciliadas/i))
      .toBeInTheDocument();
  });
});

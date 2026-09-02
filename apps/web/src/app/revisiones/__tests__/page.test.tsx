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
  REVIEW_PAGE_SIZE: 50,
  loadReviewInbox: mocks.loadReviewInbox,
  parseReviewFilter: (value: unknown) => value === 'todas' ? 'todas' : 'abiertas',
  parseReviewSelection: (
    query: Record<string, unknown>,
    companies: Array<{ company_id: string }>,
  ) => {
    const raw = query.empresa ?? 'todas';
    const page = query.pagina === undefined ? 0 : Number(query.pagina);
    if (typeof raw !== 'string' || !Number.isInteger(page) || page < 0 || page > 200) {
      return { valid: false, companyId: null, page: 0 };
    }
    if (raw === 'todas') return page === 0
      ? { valid: true, companyId: null, page: 0 }
      : { valid: false, companyId: null, page: 0 };
    return companies.some((company) => company.company_id === raw)
      ? { valid: true, companyId: raw, page }
      : { valid: false, companyId: null, page: 0 };
  },
  reviewInboxUrl: (filter: string, companyId: string | null = null, page = 0) => {
    const params = new URLSearchParams({ estado: filter, empresa: companyId ?? 'todas' });
    if (companyId && page > 0) params.set('pagina', String(page));
    return `/revisiones?${params.toString()}`;
  },
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
    expect(screen.getAllByText('Empresa Sintetica A')).toHaveLength(3);
    expect(screen.getByText('Ada Preparadora')).toBeInTheDocument();
    expect(screen.getByText(/sin efecto financiero/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Abrir expediente' })).toHaveAttribute(
      'href',
      '/empresas/company-synthetic-a/conciliacion?' +
        'izquierda=dataset-left&derecha=dataset-right&ventana=3&referencia=all&pagina=0&' +
        'revision=candidate-synthetic-a&bandeja_estado=abiertas&bandeja_empresa=todas' +
        '#revision-candidate-synthetic-a',
    );
    expect(screen.getByRole('link', { name: 'Abrir siguiente pendiente' }))
      .toHaveAttribute('href', expect.stringContaining('bandeja_empresa=todas'));
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

  it('pagina una empresa sin perder el filtro de estado', async () => {
    mocks.loadReviewInbox.mockResolvedValue([
      { company, access: 'available', truncated: true, items: [item] },
    ]);
    render(await ReviewsPage({ searchParams: Promise.resolve({
      estado: 'abiertas', empresa: company.company_id, pagina: '2',
    }) }));

    expect(mocks.loadReviewInbox).toHaveBeenCalledWith(
      'token-synthetic', [company], 'abiertas', 100, 50,
    );
    expect(screen.getByText(/pagina 3/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Pagina anterior' })).toHaveAttribute(
      'href', '/revisiones?estado=abiertas&empresa=company-synthetic-a&pagina=1',
    );
    expect(screen.getByRole('link', { name: 'Pagina siguiente' })).toHaveAttribute(
      'href', '/revisiones?estado=abiertas&empresa=company-synthetic-a&pagina=3',
    );
    expect(screen.getByRole('link', { name: 'Todas' })).toHaveAttribute(
      'href', '/revisiones?estado=todas&empresa=company-synthetic-a',
    );
  });

  it('rechaza una empresa manipulada sin consultar ni ampliar a todo el portafolio', async () => {
    render(await ReviewsPage({ searchParams: Promise.resolve({
      estado: 'abiertas', empresa: 'company-foreign',
    }) }));

    expect(mocks.loadReviewInbox).not.toHaveBeenCalled();
    expect(screen.getByText('El filtro de empresa o pagina no es valido'))
      .toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Restablecer bandeja' })).toHaveAttribute(
      'href', '/revisiones?estado=abiertas&empresa=todas',
    );
  });
});

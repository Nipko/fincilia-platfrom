import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('server-only', () => ({}));

const mocks = vi.hoisted(() => {
  class ApiError extends Error {
    readonly status: number;
    readonly code: string | null;

    constructor(status: number, message: string, code: string | null = null) {
      super(message);
      this.status = status;
      this.code = code;
    }
  }
  return {
    ApiError,
    fetchCompany: vi.fn(),
    fetchDocumentHistory: vi.fn(),
    fetchSourcesFull: vi.fn(),
    notFound: vi.fn((): never => { throw new Error('NEXT_NOT_FOUND'); }),
    readSession: vi.fn(),
    redirect: vi.fn((): never => { throw new Error('NEXT_REDIRECT'); }),
  };
});

vi.mock('next/navigation', () => ({
  notFound: mocks.notFound,
  redirect: mocks.redirect,
}));
vi.mock('@/lib/session', () => ({ readSession: mocks.readSession }));
vi.mock('@/lib/api', () => ({
  ApiError: mocks.ApiError,
  fetchCompany: mocks.fetchCompany,
  fetchDocumentHistory: mocks.fetchDocumentHistory,
  fetchSourcesFull: mocks.fetchSourcesFull,
}));

import DocumentCenterPage from '../page';

const COMPANY = '161b0037-c445-50aa-b400-72632d3f53f0';
const SOURCE = '69ad8771-aede-5cbe-9b09-2f42957e79ca';
const ARTIFACT = 'e7686c09-3300-4dca-8974-3e4aea7eb7e9';

function renderPage(query: Record<string, string> = {}) {
  return DocumentCenterPage({
    params: Promise.resolve({ companyId: COMPANY }),
    searchParams: Promise.resolve(query),
  }).then((view) => render(view));
}

function history(overrides: Record<string, unknown> = {}) {
  return {
    items: [{
      artifact_id: ARTIFACT,
      data_source_id: SOURCE,
      source_name: 'Extracto bancario sintetico',
      filename: 'extracto-agosto.csv',
      byte_size: 2048,
      content_sha256: 'a'.repeat(64),
      media_type: 'text/csv',
      status: 'stored',
      zone: 'raw',
      uploaded_at: '2026-08-26T15:30:00+00:00',
      promotion_reason: 'content_inspected',
      latest_run_kind: 'extract',
      processing_status: 'succeeded',
      processing_error: null,
      dataset_version_id: '8f9a67c4-d7a3-461c-9eaa-fd5d2d3715dd',
      dataset_state: 'published',
      completeness_state: 'verified',
      record_count: 120,
      movement_count: 119,
      rejected_count: 1,
    }],
    summary: { total: 1, raw: 1, quarantine: 0, failed: 0, legacy_unattributed: 0 },
    limit: 25,
    has_next: false,
    has_previous: false,
    next_cursor: null,
    previous_cursor: null,
    ...overrides,
  };
}

describe('DocumentCenterPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.readSession.mockResolvedValue({ token: 'token-sintetico' });
    mocks.fetchCompany.mockResolvedValue({
      company_id: COMPANY,
      legal_name: 'Espiga Sintetica SAS',
      country_code: 'CO',
      status: 'active',
      roles: ['operator'],
      firm_id: 'firm',
      engagement_id: 'engagement',
      authorization_version: 1,
      permissions: ['document.read', 'document.upload'],
    });
    mocks.fetchSourcesFull.mockResolvedValue([{
      data_source_id: SOURCE,
      source_family: 'bank_account',
      display_name: 'Extracto bancario sintetico',
      purpose_code: 'bank_statement',
      timezone: 'America/Bogota',
      status: 'active',
      closed_reason: null,
      created_at: '2026-01-01T00:00:00+00:00',
    }]);
    mocks.fetchDocumentHistory.mockResolvedValue(history());
  });

  it('presenta fuente, estado operativo y enlace al expediente sin valores financieros', async () => {
    await renderPage();

    expect(screen.getByRole('heading', { name: 'Centro de documentos' })).toBeInTheDocument();
    expect(screen.getAllByText('Extracto bancario sintetico')).toHaveLength(2);
    expect(screen.getByRole('link', { name: 'extracto-agosto.csv' })).toHaveAttribute(
      'href', `/empresas/${COMPANY}/documentos/${ARTIFACT}`,
    );
    expect(screen.getByText(/120 fila\(s\), 119 movimiento\(s\)/)).toBeInTheDocument();
    expect(history().items[0]).not.toHaveProperty('amount');
    expect(history().items[0]).not.toHaveProperty('description');
    expect(mocks.fetchDocumentHistory).toHaveBeenCalledWith(
      'token-sintetico', COMPANY,
      expect.objectContaining({ zone: 'all', processingStatus: 'all', limit: 25 }),
    );
  });

  it('preserva filtros al navegar por cursor', async () => {
    mocks.fetchDocumentHistory.mockResolvedValue(history({
      has_next: true,
      next_cursor: 'cursor-opaco',
    }));
    await renderPage({
      fuente: SOURCE,
      zona: 'quarantine',
      proceso: 'failed',
      nombre: 'agosto',
    });

    const next = screen.getByRole('link', { name: 'Mas antiguos →' });
    expect(next).toHaveAttribute('href', expect.stringContaining(`fuente=${SOURCE}`));
    expect(next).toHaveAttribute('href', expect.stringContaining('zona=quarantine'));
    expect(next).toHaveAttribute('href', expect.stringContaining('proceso=failed'));
    expect(next).toHaveAttribute('href', expect.stringContaining('nombre=agosto'));
    expect(next).toHaveAttribute('href', expect.stringContaining('cursor=cursor-opaco'));
  });

  it('distingue falta de permiso de un historico vacio', async () => {
    mocks.fetchCompany.mockResolvedValue({
      company_id: COMPANY,
      legal_name: 'Espiga Sintetica SAS',
      permissions: [],
    });
    await renderPage();

    expect(screen.getByRole('heading', {
      name: 'Sin acceso al centro de documentos',
    })).toBeInTheDocument();
    expect(screen.getByText(/no tener permiso no demuestra/i)).toBeInTheDocument();
    expect(mocks.fetchDocumentHistory).not.toHaveBeenCalled();
    expect(mocks.fetchSourcesFull).not.toHaveBeenCalled();
  });

  it('ofrece restablecer cuando el servidor rechaza un cursor', async () => {
    mocks.fetchDocumentHistory.mockRejectedValue(
      new mocks.ApiError(422, 'cursor invalido', 'document-cursor-invalid'),
    );
    await renderPage({ cursor: 'alterado' });

    expect(screen.getByRole('alert')).toHaveTextContent(/cursor que el servidor no acepta/i);
    expect(screen.getByRole('link', { name: 'Restablecer vista' })).toHaveAttribute(
      'href', `/empresas/${COMPANY}/documentos`,
    );
  });

  it('rotula de forma honesta el estado vacio', async () => {
    mocks.fetchDocumentHistory.mockResolvedValue(history({
      items: [],
      summary: { total: 0, raw: 0, quarantine: 0, failed: 0, legacy_unattributed: 0 },
    }));
    await renderPage({ nombre: 'no-existe' });

    expect(screen.getByRole('status')).toHaveTextContent(/no hay recepciones visibles/i);
  });
});

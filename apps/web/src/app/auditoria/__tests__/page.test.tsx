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
    loadAuditCenter: vi.fn(),
    readSession: vi.fn(),
    redirect: vi.fn((): never => { throw new Error('NEXT_REDIRECT'); }),
  };
});

vi.mock('next/navigation', () => ({ redirect: mocks.redirect }));
vi.mock('@/lib/session', () => ({ readSession: mocks.readSession }));
vi.mock('@/lib/api', () => ({ ApiError: mocks.ApiError, fetchMe: mocks.fetchMe }));
vi.mock('@/lib/audit-center', () => ({
  loadAuditCenter: mocks.loadAuditCenter,
  parseAuditFilter: () => ({
    companyId: null, outcome: 'all', action: '', resourceKind: '', cursor: '',
  }),
  auditEntries: (snapshots: Array<{ company: unknown; items: unknown[] }>) =>
    snapshots.flatMap((snapshot) => snapshot.items.map((event) => ({
      company: snapshot.company, event,
    }))),
}));

import AuditPage from '../page';

const company = {
  company_id: 'company-synthetic-a', legal_name: 'Empresa Sintetica A',
  country_code: 'CO', status: 'active', roles: ['auditor'],
};

const event = {
  audit_event_id: 'event-synthetic-a', action: 'document.upload',
  resource_kind: 'document', resource_ref: 'must-not-render',
  outcome: 'denied', occurred_at: '2026-08-25T12:00:00Z',
  detail: { forbidden: 'must-not-render' }, subject_id: 'subject-synthetic-a',
  actor_name: 'Ada Auditora',
};

describe('AuditPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.readSession.mockResolvedValue({ token: 'token-synthetic' });
    mocks.fetchMe.mockResolvedValue({
      display_name: 'Ada Auditora', companies: [company],
    });
  });

  it('muestra metadatos acotados sin payload ni referencia', async () => {
    mocks.loadAuditCenter.mockResolvedValue([{
      company, access: 'available', hasMore: false, nextCursor: null,
      items: [event],
    }]);
    render(await AuditPage({ searchParams: Promise.resolve({}) }));

    expect(screen.getByRole('heading', { name: 'Accesos y auditoria' }))
      .toBeInTheDocument();
    expect(screen.getAllByText('Ada Auditora')).toHaveLength(2);
    expect(screen.getByText('document.upload')).toBeInTheDocument();
    expect(screen.getByText('Denegado')).toBeInTheDocument();
    expect(screen.queryByText('must-not-render')).not.toBeInTheDocument();
  });

  it('declara una vista parcial sin certificar cero actividad', async () => {
    mocks.loadAuditCenter.mockResolvedValue([{
      company, access: 'unavailable', hasMore: false, nextCursor: null,
      items: [],
    }]);
    render(await AuditPage({ searchParams: Promise.resolve({}) }));

    expect(screen.getByText('Vista parcial.')).toBeInTheDocument();
    expect(screen.getByText(/no se presentan como cero/i)).toBeInTheDocument();
    expect(screen.getByText(/no demuestra ausencia de actividad/i))
      .toBeInTheDocument();
  });
});

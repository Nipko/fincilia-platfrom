import { describe, expect, it, vi } from 'vitest';

vi.mock('server-only', () => ({}));

import { ApiError, type AuditEvent, type CompanySummary } from '../api';
import {
  auditEntries,
  loadAuditSnapshot,
  parseAuditFilter,
} from '../audit-center';

const COMPANY: CompanySummary = {
  company_id: 'company-synthetic-a', legal_name: 'Empresa Sintetica A',
  country_code: 'CO', status: 'active', roles: ['auditor'],
};

function event(id: string, at: string, outcome = 'allowed'): AuditEvent {
  return {
    audit_event_id: id, action: 'document.read', resource_kind: 'document',
    resource_ref: 'opaque-ref', outcome, occurred_at: at, detail: {},
    subject_id: 'subject-synthetic', actor_name: 'Ada Auditora',
  };
}

function client(permissions = ['audit.read']) {
  return {
    fetchCompany: vi.fn().mockResolvedValue({
      ...COMPANY, firm_id: 'firm', engagement_id: 'engagement',
      authorization_version: 1, permissions,
    }),
    fetchAuditPage: vi.fn().mockResolvedValue({
      items: [event('b', '2026-08-25T12:00:00Z')], has_more: true,
      next_cursor: 'cursor-synthetic', limit: 25,
    }),
  };
}

const FILTER = {
  companyId: null, outcome: 'all' as const, action: '', resourceKind: '', cursor: '',
};

describe('centro de auditoria', () => {
  it('acepta solo empresa visible y filtros de forma cerrada', () => {
    expect(parseAuditFilter({
      empresa: COMPANY.company_id, resultado: 'denied',
      accion: 'document.upload', recurso: '../raw', cursor: 'bad+cursor',
    }, [COMPANY])).toEqual({
      companyId: COMPANY.company_id, outcome: 'denied',
      action: 'document.upload', resourceKind: '', cursor: '',
    });
  });

  it('no consulta eventos cuando falta audit.read', async () => {
    const api = client([]);
    const snapshot = await loadAuditSnapshot('token', COMPANY, FILTER, api);
    expect(snapshot.access).toBe('restricted');
    expect(api.fetchAuditPage).not.toHaveBeenCalled();
  });

  it('distingue revocacion, indisponibilidad y sesion vencida', async () => {
    const revoked = client();
    revoked.fetchCompany.mockRejectedValue(new ApiError(403, 'denied'));
    await expect(loadAuditSnapshot('token', COMPANY, FILTER, revoked))
      .resolves.toMatchObject({ access: 'revoked', items: [] });

    const unavailable = client();
    unavailable.fetchAuditPage.mockRejectedValue(new ApiError(503, 'down'));
    await expect(loadAuditSnapshot('token', COMPANY, FILTER, unavailable))
      .resolves.toMatchObject({ access: 'unavailable', items: [] });

    const expired = client();
    expired.fetchAuditPage.mockRejectedValue(new ApiError(401, 'expired'));
    await expect(loadAuditSnapshot('token', COMPANY, FILTER, expired))
      .rejects.toMatchObject({ status: 401 });
  });

  it('ordena globalmente sin incorporar detalle ni referencias a la vista', () => {
    const entries = auditEntries([
      { company: COMPANY, access: 'available', hasMore: false, nextCursor: null,
        items: [event('a', '2026-08-25T11:00:00Z')] },
      { company: { ...COMPANY, company_id: 'company-b' }, access: 'available',
        hasMore: false, nextCursor: null,
        items: [event('b', '2026-08-25T12:00:00Z', 'error')] },
    ]);
    expect(entries.map((item) => item.event.audit_event_id)).toEqual(['b', 'a']);
  });
});

import { describe, expect, it, vi } from 'vitest';

vi.mock('server-only', () => ({}));

import { ApiError, type CompanySummary, type MatchReview } from '../api';
import {
  loadReviewCompanySnapshot,
  MAX_REVIEW_PAGE,
  parseReviewFilter,
  parseReviewSelection,
  REVIEW_PAGE_SIZE,
  reviewInboxUrl,
  sortedReviewEntries,
} from '../review-inbox';

const COMPANY: CompanySummary = {
  company_id: 'company-synthetic-a',
  legal_name: 'Empresa Sintetica A',
  country_code: 'CO',
  status: 'active',
  roles: ['reviewer'],
};

function review(id: string, proposedAt: string): MatchReview {
  return {
    candidate_id: id,
    left_movement_id: `${id}-left`,
    right_movement_id: `${id}-right`,
    left_dataset_id: `${id}-dataset-left`,
    right_dataset_id: `${id}-dataset-right`,
    confirmation_conflict: false,
    rule_version: 'fnc-rec-exact-v1',
    signals: ['exact_amount'],
    date_window_days: 3,
    date_distance_days: 1,
    proposed_by: 'subject-ada',
    proposed_by_name: 'Ada Preparadora',
    proposed_at: proposedAt,
    status: 'open',
    decision: null,
    financial_effect: 'none',
    proves_balance_reconciliation: false,
  };
}

function client(permissions = ['movement.read']) {
  return {
    fetchCompany: vi.fn().mockResolvedValue({
      ...COMPANY,
      firm_id: 'firm-synthetic',
      engagement_id: 'engagement-synthetic',
      authorization_version: 4,
      permissions,
    }),
    fetchReviewQueue: vi.fn().mockResolvedValue({
      status: 'open', offset: 0, limit: 50, truncated: false,
      items: [review('candidate-a', '2026-08-24T12:00:00Z')],
      financial_effect: 'none', proves_balance_reconciliation: false,
    }),
  };
}

describe('bandeja multiempresa', () => {
  it('normaliza el filtro en un vocabulario cerrado', () => {
    expect(parseReviewFilter('confirmadas')).toBe('confirmadas');
    expect(parseReviewFilter('automaticas')).toBe('abiertas');
    expect(parseReviewFilter(['todas'])).toBe('abiertas');
  });

  it('selecciona todas o una empresa autorizada y limita la pagina', () => {
    expect(parseReviewSelection({}, [COMPANY])).toEqual({
      valid: true, companyId: null, page: 0,
    });
    expect(parseReviewSelection({ empresa: COMPANY.company_id, pagina: '2' }, [COMPANY]))
      .toEqual({ valid: true, companyId: COMPANY.company_id, page: 2 });
    expect(parseReviewSelection({ empresa: 'otra-empresa' }, [COMPANY]).valid).toBe(false);
    expect(parseReviewSelection({ empresa: [COMPANY.company_id] }, [COMPANY]).valid).toBe(false);
    expect(parseReviewSelection({ empresa: COMPANY.company_id, pagina: ['1'] }, [COMPANY]).valid)
      .toBe(false);
    expect(parseReviewSelection({ empresa: COMPANY.company_id,
      pagina: String(MAX_REVIEW_PAGE + 1) }, [COMPANY]).valid).toBe(false);
    expect(parseReviewSelection({ empresa: 'todas', pagina: '1' }, [COMPANY]).valid)
      .toBe(false);
  });

  it('construye enlaces cerrados y omite pagina en el portafolio completo', () => {
    expect(reviewInboxUrl('confirmadas')).toBe(
      '/revisiones?estado=confirmadas&empresa=todas',
    );
    expect(reviewInboxUrl('rechazadas', COMPANY.company_id, 3)).toBe(
      '/revisiones?estado=rechazadas&empresa=company-synthetic-a&pagina=3',
    );
  });

  it('no consulta expedientes sin movement.read ni presenta cero como disponible', async () => {
    const api = client([]);
    const snapshot = await loadReviewCompanySnapshot(
      'token-synthetic', COMPANY, 'open', api,
    );
    expect(snapshot.access).toBe('restricted');
    expect(snapshot.items).toEqual([]);
    expect(api.fetchReviewQueue).not.toHaveBeenCalled();
  });

  it('propaga offset y limite acotados a la consulta por empresa', async () => {
    const api = client();
    await loadReviewCompanySnapshot(
      'token-synthetic', COMPANY, 'open', api, REVIEW_PAGE_SIZE * 2, REVIEW_PAGE_SIZE,
    );
    expect(api.fetchReviewQueue).toHaveBeenCalledWith(
      'token-synthetic', COMPANY.company_id, 'open', 100, 50,
    );
  });

  it('conserva revocacion, fallo parcial y expiracion como estados distintos', async () => {
    const revoked = client();
    revoked.fetchCompany.mockRejectedValue(new ApiError(404, 'hidden'));
    await expect(loadReviewCompanySnapshot(
      'token-synthetic', COMPANY, 'open', revoked,
    )).resolves.toMatchObject({ access: 'revoked', items: [] });

    const partial = client();
    partial.fetchReviewQueue.mockRejectedValue(new ApiError(503, 'down'));
    await expect(loadReviewCompanySnapshot(
      'token-synthetic', COMPANY, 'open', partial,
    )).resolves.toMatchObject({ access: 'unavailable', items: [] });

    const expired = client();
    expired.fetchReviewQueue.mockRejectedValue(new ApiError(401, 'expired'));
    await expect(loadReviewCompanySnapshot(
      'token-synthetic', COMPANY, 'open', expired,
    )).rejects.toMatchObject({ status: 401 });
  });

  it('prioriza el expediente mas antiguo sin mezclar valores financieros', () => {
    const another = { ...COMPANY, company_id: 'company-b', legal_name: 'Empresa B' };
    const entries = sortedReviewEntries([
      { company: COMPANY, access: 'available', truncated: false,
        items: [review('later', '2026-08-24T13:00:00Z')] },
      { company: another, access: 'available', truncated: false,
        items: [review('earlier', '2026-08-24T11:00:00Z')] },
    ]);
    expect(entries.map((item) => item.review.candidate_id)).toEqual([
      'earlier', 'later',
    ]);
    expect(JSON.stringify(entries)).not.toMatch(/"amount"|"balance"/);
  });
});

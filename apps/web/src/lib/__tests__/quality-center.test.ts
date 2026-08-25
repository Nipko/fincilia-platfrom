import { describe, expect, it, vi } from 'vitest';

vi.mock('server-only', () => ({}));

import { ApiError, type CompanySummary, type QualityIssuePage } from '../api';
import {
  aggregateQualitySummary,
  loadQualityCompanySnapshot,
  parseQualitySeverity,
  parseQualityStatus,
  qualityHref,
  selectQualityCompanies,
  sortedQualityEntries,
} from '../quality-center';

const company: CompanySummary = {
  company_id: 'company-a', legal_name: 'Alfa SAS', country_code: 'CO',
  status: 'active', roles: ['preparer'],
};

const page: QualityIssuePage = {
  filter: { status: 'open', severity: 'all', rule: 'all' },
  offset: 0, limit: 100, truncated: false,
  summary: {
    total: 2, open: 1, acknowledged: 1, resolved: 0, dismissed: 0,
    high: 1, warning: 1, info: 0,
  },
  items: [{
    issue_id: 'issue-a', rule_code: 'lineage_invalidated',
    rule_version: 'quality-rules-v1', scope_kind: 'dataset', scope_ref: 'dataset-a',
    severity: 'high', status: 'open', occurrence_count: 1,
    assigned_to: null, assigned_to_name: null, reviewed_by: null,
    reviewed_by_name: null, resolution_reason: null,
    first_seen_at: '2026-08-20T00:00:00Z', last_seen_at: '2026-08-24T00:00:00Z',
    updated_at: '2026-08-24T00:00:00Z', financial_effect: 'none', proves_fraud: false,
  }],
  notice: 'quality_signal_only',
};

describe('quality center', () => {
  it('fails closed to open and all for unknown filters', () => {
    expect(parseQualityStatus('invented')).toBe('open');
    expect(parseQualitySeverity('critical')).toBe('all');
  });

  it('never accepts an unknown company selector', () => {
    expect(selectQualityCompanies([company], 'unknown')).toEqual([company]);
  });

  it('distinguishes read from manage permission', async () => {
    const snapshot = await loadQualityCompanySnapshot('token', company, 'open', 'all', {
      fetchCompany: vi.fn().mockResolvedValue({ ...company, firm_id: 'firm',
        engagement_id: 'engagement', authorization_version: 1,
        permissions: ['quality.read'] }),
      fetchQualityIssues: vi.fn().mockResolvedValue(page),
    });
    expect(snapshot.access).toBe('available');
    expect(snapshot.canManage).toBe(false);
  });

  it('does not turn a revoked company into an empty healthy result', async () => {
    const snapshot = await loadQualityCompanySnapshot('token', company, 'open', 'all', {
      fetchCompany: vi.fn().mockRejectedValue(new ApiError(403, 'denied')),
      fetchQualityIssues: vi.fn(),
    });
    expect(snapshot).toMatchObject({ access: 'revoked', page: null });
  });

  it('sorts high severity and aggregates only available snapshots', () => {
    const snapshots = [
      { company, access: 'available' as const, canManage: true, page },
      { company: { ...company, company_id: 'company-b' },
        access: 'unavailable' as const, canManage: false, page: null },
    ];
    expect(sortedQualityEntries(snapshots)[0]?.issue.severity).toBe('high');
    expect(aggregateQualitySummary(snapshots)).toEqual(page.summary);
  });

  it('preserves status severity and explicit company in navigation', () => {
    expect(qualityHref('acknowledged', 'warning', 'company-a')).toBe(
      '/calidad?estado=acknowledged&severidad=warning&empresa=company-a');
  });
});

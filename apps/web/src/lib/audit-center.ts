import {
  ApiError,
  fetchAuditPage,
  fetchCompany,
  type AuditEvent,
  type AuditFilters,
  type CompanySummary,
} from './api';

export type AuditAccess = 'available' | 'restricted' | 'revoked' | 'unavailable';
export type AuditOutcomeFilter = 'all' | 'allowed' | 'denied' | 'error';

export type AuditCenterFilter = {
  companyId: string | null;
  outcome: AuditOutcomeFilter;
  action: string;
  resourceKind: string;
  cursor: string;
};

export type AuditSnapshot = {
  company: CompanySummary;
  access: AuditAccess;
  items: AuditEvent[];
  hasMore: boolean;
  nextCursor: string | null;
};

export function safeToken(value: unknown): string {
  return typeof value === 'string' && /^[a-z][a-z0-9_.-]{0,99}$/.test(value)
    ? value
    : '';
}

export function safeCursor(value: unknown): string {
  return typeof value === 'string' && /^[A-Za-z0-9_-]{1,256}$/.test(value)
    ? value
    : '';
}

export function parseAuditFilter(
  query: Record<string, string | string[] | undefined>,
  companies: CompanySummary[],
): AuditCenterFilter {
  const scalar = (value: string | string[] | undefined) =>
    typeof value === 'string' ? value : '';
  const requestedCompany = scalar(query.empresa);
  const outcome = scalar(query.resultado);
  return {
    companyId: companies.some((item) => item.company_id === requestedCompany)
      ? requestedCompany
      : null,
    outcome: ['allowed', 'denied', 'error'].includes(outcome)
      ? outcome as AuditOutcomeFilter
      : 'all',
    action: safeToken(scalar(query.accion)),
    resourceKind: safeToken(scalar(query.recurso)),
    cursor: safeCursor(scalar(query.cursor)),
  };
}

type AuditClient = {
  fetchCompany: typeof fetchCompany;
  fetchAuditPage: typeof fetchAuditPage;
};

const defaultClient: AuditClient = { fetchCompany, fetchAuditPage };

export async function loadAuditSnapshot(
  token: string,
  company: CompanySummary,
  filter: AuditCenterFilter,
  client: AuditClient = defaultClient,
): Promise<AuditSnapshot> {
  try {
    const detail = await client.fetchCompany(token, company.company_id);
    if (!detail.permissions.includes('audit.read')) {
      return { company, access: 'restricted', items: [], hasMore: false,
        nextCursor: null };
    }
    const query: AuditFilters = { limit: filter.companyId ? 50 : 25 };
    if (filter.action) query.action = filter.action;
    if (filter.outcome !== 'all') query.outcome = filter.outcome;
    if (filter.resourceKind) query.resourceKind = filter.resourceKind;
    if (filter.companyId === company.company_id && filter.cursor) {
      query.cursor = filter.cursor;
    }
    const page = await client.fetchAuditPage(token, company.company_id, query);
    return { company, access: 'available', items: page.items,
      hasMore: page.has_more, nextCursor: page.next_cursor };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) throw error;
    if (error instanceof ApiError && [403, 404].includes(error.status)) {
      return { company, access: 'revoked', items: [], hasMore: false,
        nextCursor: null };
    }
    return { company, access: 'unavailable', items: [], hasMore: false,
      nextCursor: null };
  }
}

export async function loadAuditCenter(
  token: string,
  companies: CompanySummary[],
  filter: AuditCenterFilter,
  client: AuditClient = defaultClient,
): Promise<AuditSnapshot[]> {
  const selected = filter.companyId
    ? companies.filter((item) => item.company_id === filter.companyId)
    : companies;
  return Promise.all(selected.map((company) =>
    loadAuditSnapshot(token, company, filter, client)));
}

export function auditEntries(snapshots: AuditSnapshot[]) {
  return snapshots.flatMap((snapshot) => snapshot.items.map((event) => ({
    company: snapshot.company,
    event,
  }))).sort((left, right) =>
    right.event.occurred_at.localeCompare(left.event.occurred_at)
    || right.event.audit_event_id.localeCompare(left.event.audit_event_id));
}

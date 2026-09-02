import 'server-only';

import {
  ApiError,
  fetchCompany,
  fetchReviewQueue,
  type CompanySummary,
  type MatchReview,
  type ReviewQueueStatus,
} from './api';
import { mapWithConcurrency } from './portfolio';

export type ReviewInboxFilter = 'abiertas' | 'confirmadas' | 'rechazadas' | 'todas';
export const REVIEW_PAGE_SIZE = 50;
export const MAX_REVIEW_PAGE = 200;
type QueryValue = string | string[] | undefined;

export type ReviewInboxSelection = {
  valid: boolean;
  companyId: string | null;
  page: number;
};
export type ReviewCompanyAccess =
  | 'available'
  | 'restricted'
  | 'revoked'
  | 'unavailable';

export type ReviewCompanySnapshot = {
  company: CompanySummary;
  access: ReviewCompanyAccess;
  items: MatchReview[];
  truncated: boolean;
};

type ReviewInboxClient = {
  fetchCompany: typeof fetchCompany;
  fetchReviewQueue: typeof fetchReviewQueue;
};

const DEFAULT_CLIENT: ReviewInboxClient = { fetchCompany, fetchReviewQueue };

const FILTER_TO_STATUS: Record<ReviewInboxFilter, ReviewQueueStatus> = {
  abiertas: 'open',
  confirmadas: 'confirmed',
  rechazadas: 'rejected',
  todas: 'all',
};

export function parseReviewFilter(value: string | string[] | undefined): ReviewInboxFilter {
  return typeof value === 'string' && value in FILTER_TO_STATUS
    ? (value as ReviewInboxFilter)
    : 'abiertas';
}

export function reviewStatus(filter: ReviewInboxFilter): ReviewQueueStatus {
  return FILTER_TO_STATUS[filter];
}

function single(value: QueryValue): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed || null;
}

function reviewPage(value: QueryValue): number | null {
  if (value === undefined) return 0;
  const raw = single(value);
  if (raw === null || !/^\d+$/.test(raw)) return null;
  const page = Number(raw);
  return Number.isSafeInteger(page) && page <= MAX_REVIEW_PAGE ? page : null;
}

export function parseReviewSelection(
  query: Record<string, QueryValue>,
  companies: readonly CompanySummary[],
): ReviewInboxSelection {
  const rawCompany = query.empresa === undefined ? 'todas' : single(query.empresa);
  const page = reviewPage(query.pagina);
  if (rawCompany === null || page === null) {
    return { valid: false, companyId: null, page: 0 };
  }
  if (rawCompany === 'todas') {
    return page === 0
      ? { valid: true, companyId: null, page: 0 }
      : { valid: false, companyId: null, page: 0 };
  }
  const authorised = companies.some((company) => company.company_id === rawCompany);
  return authorised
    ? { valid: true, companyId: rawCompany, page }
    : { valid: false, companyId: null, page: 0 };
}

export function reviewInboxUrl(
  filter: ReviewInboxFilter,
  companyId: string | null = null,
  page = 0,
): string {
  const params = new URLSearchParams({
    estado: filter,
    empresa: companyId ?? 'todas',
  });
  if (companyId && page > 0) params.set('pagina', String(page));
  return `/revisiones?${params.toString()}`;
}

export async function loadReviewCompanySnapshot(
  token: string,
  company: CompanySummary,
  status: ReviewQueueStatus,
  client: ReviewInboxClient = DEFAULT_CLIENT,
  offset = 0,
  limit = REVIEW_PAGE_SIZE,
): Promise<ReviewCompanySnapshot> {
  let detail;
  try {
    detail = await client.fetchCompany(token, company.company_id);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) throw error;
    const access = error instanceof ApiError
      && (error.status === 403 || error.status === 404)
      ? 'revoked'
      : 'unavailable';
    return { company, access, items: [], truncated: false };
  }

  if (!detail.permissions.includes('movement.read')) {
    return { company, access: 'restricted', items: [], truncated: false };
  }

  try {
    const page = await client.fetchReviewQueue(
      token, company.company_id, status, offset, limit,
    );
    return {
      company,
      access: 'available',
      items: page.items,
      truncated: page.truncated,
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) throw error;
    return {
      company,
      access: error instanceof ApiError && error.status === 403
        ? 'restricted'
        : 'unavailable',
      items: [],
      truncated: false,
    };
  }
}

export async function loadReviewInbox(
  token: string,
  companies: readonly CompanySummary[],
  filter: ReviewInboxFilter,
  offset = 0,
  limit = REVIEW_PAGE_SIZE,
): Promise<ReviewCompanySnapshot[]> {
  const status = reviewStatus(filter);
  return mapWithConcurrency(companies, 4, (company) =>
    loadReviewCompanySnapshot(token, company, status, DEFAULT_CLIENT, offset, limit),
  );
}

export function sortedReviewEntries(snapshots: readonly ReviewCompanySnapshot[]) {
  return snapshots
    .flatMap((snapshot) => snapshot.items.map((review) => ({
      company: snapshot.company,
      review,
    })))
    .sort((left, right) =>
      left.review.proposed_at.localeCompare(right.review.proposed_at)
      || left.company.legal_name.localeCompare(right.company.legal_name)
      || left.review.candidate_id.localeCompare(right.review.candidate_id));
}

export function formatReviewTimestamp(value: string): string {
  return `${new Date(value).toISOString().slice(0, 16).replace('T', ' ')} UTC`;
}

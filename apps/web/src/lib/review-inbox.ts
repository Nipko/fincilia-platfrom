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

export async function loadReviewCompanySnapshot(
  token: string,
  company: CompanySummary,
  status: ReviewQueueStatus,
  client: ReviewInboxClient = DEFAULT_CLIENT,
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
      token, company.company_id, status, 0, 50,
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
): Promise<ReviewCompanySnapshot[]> {
  const status = reviewStatus(filter);
  return mapWithConcurrency(companies, 4, (company) =>
    loadReviewCompanySnapshot(token, company, status),
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

import 'server-only';

import {
  ApiError,
  fetchCloseReviewPackets,
  fetchCloseReviewers,
  fetchCompany,
  type CloseReviewPacket,
  type CloseReviewReviewer,
  type CompanySummary,
} from './api';
import { mapWithConcurrency } from './portfolio';

export type CloseReviewAccess =
  | 'available'
  | 'restricted'
  | 'revoked'
  | 'unavailable';

export type CloseReviewSnapshot = {
  company: CompanySummary;
  access: CloseReviewAccess;
  permissions: string[];
  reviewers: CloseReviewReviewer[];
  packets: CloseReviewPacket[];
};

type CloseReviewClient = {
  fetchCompany: typeof fetchCompany;
  fetchCloseReviewPackets: typeof fetchCloseReviewPackets;
  fetchCloseReviewers: typeof fetchCloseReviewers;
};

const CLIENT: CloseReviewClient = {
  fetchCompany,
  fetchCloseReviewPackets,
  fetchCloseReviewers,
};

export async function loadCloseReviewCompany(
  token: string,
  company: CompanySummary,
  client: CloseReviewClient = CLIENT,
): Promise<CloseReviewSnapshot> {
  let detail;
  try {
    detail = await client.fetchCompany(token, company.company_id);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) throw error;
    return {
      company,
      access: error instanceof ApiError && [403, 404].includes(error.status)
        ? 'revoked' : 'unavailable',
      permissions: [], reviewers: [], packets: [],
    };
  }
  if (!detail.permissions.includes('report.read')) {
    return {
      company, access: 'restricted', permissions: detail.permissions,
      reviewers: [], packets: [],
    };
  }
  try {
    const [packetPage, reviewers] = await Promise.all([
      client.fetchCloseReviewPackets(token, company.company_id, 100),
      detail.permissions.includes('close.prepare')
        ? client.fetchCloseReviewers(token, company.company_id)
        : Promise.resolve([]),
    ]);
    return {
      company, access: 'available', permissions: detail.permissions,
      reviewers, packets: packetPage.items,
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) throw error;
    return {
      company,
      access: error instanceof ApiError && [403, 404].includes(error.status)
        ? 'restricted' : 'unavailable',
      permissions: detail.permissions, reviewers: [], packets: [],
    };
  }
}

export function loadCloseReviewCenter(
  token: string,
  companies: readonly CompanySummary[],
): Promise<CloseReviewSnapshot[]> {
  return mapWithConcurrency(companies, 3, (company) =>
    loadCloseReviewCompany(token, company));
}

export function packetsForPeriod(
  snapshot: CloseReviewSnapshot | undefined,
  periodStart: string,
  periodEnd: string,
): CloseReviewPacket[] {
  return snapshot?.packets.filter((packet) =>
    packet.period_start === periodStart && packet.period_end === periodEnd) ?? [];
}

import 'server-only';

import {
  ApiError,
  fetchCompany,
  fetchQualityIssues,
  type CompanySummary,
  type QualityIssue,
  type QualityIssuePage,
  type QualitySeverity,
  type QualityStatus,
} from './api';
import { mapWithConcurrency } from './portfolio';

export type QualityStatusFilter = QualityStatus | 'all';
export type QualitySeverityFilter = QualitySeverity | 'all';

export type QualityCompanySnapshot = {
  company: CompanySummary;
  access: 'available' | 'restricted' | 'revoked' | 'unavailable';
  canManage: boolean;
  page: QualityIssuePage | null;
};

type QualityClient = {
  fetchCompany: typeof fetchCompany;
  fetchQualityIssues: typeof fetchQualityIssues;
};

const DEFAULT_CLIENT: QualityClient = { fetchCompany, fetchQualityIssues };

export function parseQualityStatus(value: string | string[] | undefined): QualityStatusFilter {
  return typeof value === 'string'
    && ['open', 'acknowledged', 'resolved', 'dismissed', 'all'].includes(value)
    ? value as QualityStatusFilter
    : 'open';
}

export function parseQualitySeverity(
  value: string | string[] | undefined,
): QualitySeverityFilter {
  return typeof value === 'string' && ['high', 'warning', 'info', 'all'].includes(value)
    ? value as QualitySeverityFilter
    : 'all';
}

export function selectQualityCompanies(
  companies: readonly CompanySummary[],
  requested: string | string[] | undefined,
): CompanySummary[] {
  if (typeof requested !== 'string' || requested === 'todas') return [...companies];
  const selected = companies.find((company) => company.company_id === requested);
  return selected ? [selected] : [...companies];
}

export async function loadQualityCompanySnapshot(
  token: string,
  company: CompanySummary,
  status: QualityStatusFilter,
  severity: QualitySeverityFilter,
  client: QualityClient = DEFAULT_CLIENT,
): Promise<QualityCompanySnapshot> {
  let detail;
  try {
    detail = await client.fetchCompany(token, company.company_id);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) throw error;
    return {
      company,
      access: error instanceof ApiError && [403, 404].includes(error.status)
        ? 'revoked'
        : 'unavailable',
      canManage: false,
      page: null,
    };
  }
  if (!detail.permissions.includes('quality.read')) {
    return { company, access: 'restricted', canManage: false, page: null };
  }
  try {
    const page = await client.fetchQualityIssues(token, company.company_id, {
      status,
      severity,
      limit: 100,
    });
    return {
      company,
      access: 'available',
      canManage: detail.permissions.includes('quality.manage'),
      page,
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) throw error;
    return {
      company,
      access: error instanceof ApiError && error.status === 403
        ? 'restricted'
        : 'unavailable',
      canManage: false,
      page: null,
    };
  }
}

export function loadQualityCenter(
  token: string,
  companies: readonly CompanySummary[],
  status: QualityStatusFilter,
  severity: QualitySeverityFilter,
): Promise<QualityCompanySnapshot[]> {
  return mapWithConcurrency(companies, 4, (company) =>
    loadQualityCompanySnapshot(token, company, status, severity),
  );
}

export type QualityEntry = {
  company: CompanySummary;
  canManage: boolean;
  issue: QualityIssue;
};

const SEVERITY_PRIORITY: Record<QualitySeverity, number> = {
  high: 0,
  warning: 1,
  info: 2,
};

export function sortedQualityEntries(
  snapshots: readonly QualityCompanySnapshot[],
): QualityEntry[] {
  return snapshots.flatMap((snapshot) =>
    snapshot.page?.items.map((issue) => ({
      company: snapshot.company,
      canManage: snapshot.canManage,
      issue,
    })) ?? [],
  ).sort((left, right) =>
    SEVERITY_PRIORITY[left.issue.severity] - SEVERITY_PRIORITY[right.issue.severity]
    || right.issue.last_seen_at.localeCompare(left.issue.last_seen_at)
    || left.company.legal_name.localeCompare(right.company.legal_name)
    || left.issue.issue_id.localeCompare(right.issue.issue_id));
}

export function aggregateQualitySummary(
  snapshots: readonly QualityCompanySnapshot[],
): QualityIssuePage['summary'] {
  const result: QualityIssuePage['summary'] = {
    total: 0,
    open: 0,
    acknowledged: 0,
    resolved: 0,
    dismissed: 0,
    high: 0,
    warning: 0,
    info: 0,
  };
  for (const snapshot of snapshots) {
    if (!snapshot.page) continue;
    for (const key of Object.keys(result) as (keyof typeof result)[]) {
      result[key] += snapshot.page.summary[key];
    }
  }
  return result;
}

export function qualityHref(
  status: QualityStatusFilter,
  severity: QualitySeverityFilter,
  companyId: string | undefined,
): string {
  const query = new URLSearchParams({ estado: status, severidad: severity });
  if (companyId && companyId !== 'todas') query.set('empresa', companyId);
  return `/calidad?${query.toString()}`;
}

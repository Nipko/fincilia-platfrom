import 'server-only';

import {
  ApiError,
  fetchCompany,
  fetchOperationalReport,
  type CompanySummary,
  type OperationalReport,
} from './api';
import { mapWithConcurrency } from './portfolio';

export type ReportDays = 30 | 90 | 180 | 365;

export type CompanyReportSnapshot = {
  company: CompanySummary;
  access: 'available' | 'restricted' | 'revoked' | 'unavailable';
  canExport: boolean;
  report: OperationalReport | null;
};

type ReportClient = {
  fetchCompany: typeof fetchCompany;
  fetchOperationalReport: typeof fetchOperationalReport;
};

const CLIENT: ReportClient = { fetchCompany, fetchOperationalReport };

export function parseReportDays(value: string | string[] | undefined): ReportDays {
  if (typeof value === 'string' && ['30', '90', '180', '365'].includes(value)) {
    return Number(value) as ReportDays;
  }
  return 90;
}

export function parseReportDate(
  value: string | string[] | undefined,
  today = new Date().toISOString().slice(0, 10),
): string | undefined {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return undefined;
  const parsed = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(parsed.valueOf()) || parsed.toISOString().slice(0, 10) !== value) {
    return undefined;
  }
  return value <= today && value >= '2000-01-01' ? value : undefined;
}

export function selectReportCompanies(
  companies: readonly CompanySummary[],
  requested: string | string[] | undefined,
): CompanySummary[] {
  if (typeof requested !== 'string' || requested === 'todas') return [...companies];
  const selected = companies.find((company) => company.company_id === requested);
  return selected ? [selected] : [...companies];
}

export async function loadCompanyReport(
  token: string,
  company: CompanySummary,
  days: ReportDays,
  asOf: string | undefined,
  client: ReportClient = CLIENT,
): Promise<CompanyReportSnapshot> {
  let detail;
  try {
    detail = await client.fetchCompany(token, company.company_id);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) throw error;
    return {
      company,
      access: error instanceof ApiError && [403, 404].includes(error.status)
        ? 'revoked' : 'unavailable',
      canExport: false,
      report: null,
    };
  }
  if (!detail.permissions.includes('report.read')) {
    return { company, access: 'restricted', canExport: false, report: null };
  }
  try {
    const report = await client.fetchOperationalReport(
      token, company.company_id, days, asOf);
    return {
      company,
      access: 'available',
      canExport: detail.permissions.includes('report.export'),
      report,
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) throw error;
    return {
      company,
      access: error instanceof ApiError && [403, 404].includes(error.status)
        ? 'restricted' : 'unavailable',
      canExport: false,
      report: null,
    };
  }
}

export function loadReportCenter(
  token: string,
  companies: readonly CompanySummary[],
  days: ReportDays,
  asOf?: string,
): Promise<CompanyReportSnapshot[]> {
  return mapWithConcurrency(companies, 3, (company) =>
    loadCompanyReport(token, company, days, asOf));
}

export function aggregateOperationalCounts(
  snapshots: readonly CompanyReportSnapshot[],
): { documents: number; datasets: number; movements: number;
     pendingReviews: number; activeHigh: number } {
  const total = {
    documents: 0, datasets: 0, movements: 0, pendingReviews: 0, activeHigh: 0,
  };
  for (const { report } of snapshots) {
    if (!report) continue;
    total.documents += report.summary.documents.total;
    total.datasets += report.summary.datasets.total;
    total.movements += report.summary.datasets.movements;
    total.pendingReviews += report.summary.reconciliation.pending;
    total.activeHigh += report.summary.quality.active_high;
  }
  return total;
}

export function reportHref(companyId: string, days: ReportDays, asOf?: string): string {
  const query = new URLSearchParams({ days: String(days) });
  if (asOf) query.set('as_of', asOf);
  return `/api/companies/${encodeURIComponent(companyId)}/reports/operational?${query}`;
}

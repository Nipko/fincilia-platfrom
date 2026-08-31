import 'server-only';

import {
  ApiError,
  fetchAccountingPeriods,
  fetchCompany,
  type AccountingPeriodClose,
  type CompanySummary,
} from './api';
import { mapWithConcurrency } from './portfolio';

export type ClosePeriodSnapshot = {
  company: CompanySummary;
  access: 'available' | 'restricted' | 'revoked' | 'unavailable';
  permissions: string[];
  periods: AccountingPeriodClose[];
};

export async function loadClosePeriodCompany(
  token: string,
  company: CompanySummary,
): Promise<ClosePeriodSnapshot> {
  let detail;
  try {
    detail = await fetchCompany(token, company.company_id);
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) {
      return { company, access: 'restricted', permissions: [], periods: [] };
    }
    if (error instanceof ApiError && error.status === 401) throw error;
    return { company, access: 'unavailable', permissions: [], periods: [] };
  }
  try {
    const page = await fetchAccountingPeriods(token, company.company_id, 100);
    return {
      company, access: 'available', permissions: detail.permissions,
      periods: page.items,
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) throw error;
    if (error instanceof ApiError && error.status === 403) {
      return { company, access: 'revoked', permissions: [], periods: [] };
    }
    return { company, access: 'unavailable', permissions: detail.permissions, periods: [] };
  }
}

export function loadClosePeriodCenter(
  token: string,
  companies: readonly CompanySummary[],
): Promise<ClosePeriodSnapshot[]> {
  return mapWithConcurrency(companies, 3, (company) =>
    loadClosePeriodCompany(token, company));
}

export function closeForPeriod(
  snapshot: ClosePeriodSnapshot | undefined,
  periodStart: string,
  periodEnd: string,
): AccountingPeriodClose | undefined {
  return snapshot?.periods.find((period) =>
    period.period_start === periodStart && period.period_end === periodEnd
    && period.status !== 'reopened')
    ?? snapshot?.periods.find((period) =>
      period.period_start === periodStart && period.period_end === periodEnd);
}

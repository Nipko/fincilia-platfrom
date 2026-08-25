import 'server-only';

import {
  ApiError,
  fetchCompany,
  fetchOperationalPeriods,
  type CompanySummary,
  type OperationalFilter,
  type OperationalPeriod,
  type OperationalPeriodPage,
  type OperationalSummary,
} from './api';
import { mapWithConcurrency } from './portfolio';

export type OperationsFilter =
  | 'atencion'
  | 'vencidos'
  | 'gracia'
  | 'hoy'
  | 'proximos'
  | 'futuros'
  | 'recibidos'
  | 'dispensados'
  | 'todos';

export type OperationsCompanyAccess =
  | 'available'
  | 'restricted'
  | 'revoked'
  | 'unavailable';

export type OperationsCompanySnapshot = {
  company: CompanySummary;
  access: OperationsCompanyAccess;
  page: OperationalPeriodPage | null;
};

const FILTER_TO_API: Record<OperationsFilter, OperationalFilter> = {
  atencion: 'attention',
  vencidos: 'overdue',
  gracia: 'in_grace',
  hoy: 'due_today',
  proximos: 'due_soon',
  futuros: 'upcoming',
  recibidos: 'satisfied',
  dispensados: 'waived',
  todos: 'all',
};

const PRIORITY: Record<OperationalPeriod['reminder_state'], number> = {
  overdue: 0,
  in_grace: 1,
  due_today: 2,
  due_soon: 3,
  upcoming: 4,
  satisfied: 5,
  waived: 6,
};

type OperationsClient = {
  fetchCompany: typeof fetchCompany;
  fetchOperationalPeriods: typeof fetchOperationalPeriods;
};

const DEFAULT_CLIENT: OperationsClient = {
  fetchCompany,
  fetchOperationalPeriods,
};

export function parseOperationsFilter(
  value: string | string[] | undefined,
): OperationsFilter {
  return typeof value === 'string' && value in FILTER_TO_API
    ? value as OperationsFilter
    : 'atencion';
}

export function apiOperationsFilter(filter: OperationsFilter): OperationalFilter {
  return FILTER_TO_API[filter];
}

export function selectCompanies(
  companies: readonly CompanySummary[],
  requested: string | string[] | undefined,
): CompanySummary[] {
  if (typeof requested !== 'string' || requested === 'todas') return [...companies];
  const selected = companies.find((company) => company.company_id === requested);
  return selected ? [selected] : [...companies];
}

export async function loadOperationsCompanySnapshot(
  token: string,
  company: CompanySummary,
  filter: OperationalFilter,
  client: OperationsClient = DEFAULT_CLIENT,
): Promise<OperationsCompanySnapshot> {
  let detail;
  try {
    detail = await client.fetchCompany(token, company.company_id);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) throw error;
    const access = error instanceof ApiError
      && (error.status === 403 || error.status === 404)
      ? 'revoked'
      : 'unavailable';
    return { company, access, page: null };
  }

  if (!detail.permissions.includes('data_source.manage')) {
    return { company, access: 'restricted', page: null };
  }

  try {
    const page = await client.fetchOperationalPeriods(
      token, company.company_id, filter, 50,
    );
    return { company, access: 'available', page };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) throw error;
    return {
      company,
      access: error instanceof ApiError && error.status === 403
        ? 'restricted'
        : 'unavailable',
      page: null,
    };
  }
}

export function loadOperationsCenter(
  token: string,
  companies: readonly CompanySummary[],
  filter: OperationsFilter,
): Promise<OperationsCompanySnapshot[]> {
  const apiFilter = apiOperationsFilter(filter);
  return mapWithConcurrency(companies, 4, (company) =>
    loadOperationsCompanySnapshot(token, company, apiFilter),
  );
}

export type OperationalEntry = {
  company: CompanySummary;
  period: OperationalPeriod;
};

export function sortedOperationalEntries(
  snapshots: readonly OperationsCompanySnapshot[],
): OperationalEntry[] {
  return snapshots
    .flatMap((snapshot) => snapshot.page?.items.map((period) => ({
      company: snapshot.company,
      period,
    })) ?? [])
    .sort((left, right) =>
      PRIORITY[left.period.reminder_state] - PRIORITY[right.period.reminder_state]
      || left.period.due_on.localeCompare(right.period.due_on)
      || left.company.legal_name.localeCompare(right.company.legal_name)
      || left.period.expectation_id.localeCompare(right.period.expectation_id));
}

export function aggregateOperationalSummary(
  snapshots: readonly OperationsCompanySnapshot[],
): OperationalSummary {
  const result: OperationalSummary = {
    period_count: 0,
    source_count: 0,
    overdue: 0,
    in_grace: 0,
    due_today: 0,
    due_soon: 0,
    upcoming: 0,
    satisfied: 0,
    waived: 0,
    filtered_total: 0,
    oldest_due_on: null,
    newest_due_on: null,
  };
  for (const snapshot of snapshots) {
    if (!snapshot.page) continue;
    const summary = snapshot.page.summary;
    for (const key of [
      'period_count', 'source_count', 'overdue', 'in_grace', 'due_today',
      'due_soon', 'upcoming', 'satisfied', 'waived', 'filtered_total',
    ] as const) {
      result[key] += summary[key];
    }
    if (summary.oldest_due_on
      && (!result.oldest_due_on || summary.oldest_due_on < result.oldest_due_on)) {
      result.oldest_due_on = summary.oldest_due_on;
    }
    if (summary.newest_due_on
      && (!result.newest_due_on || summary.newest_due_on > result.newest_due_on)) {
      result.newest_due_on = summary.newest_due_on;
    }
  }
  return result;
}

export function operationsHref(
  filter: OperationsFilter,
  companyId: string | undefined,
): string {
  const query = new URLSearchParams({ estado: filter });
  if (companyId && companyId !== 'todas') query.set('empresa', companyId);
  return `/recordatorios?${query.toString()}`;
}

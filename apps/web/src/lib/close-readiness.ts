import 'server-only';

import {
  ApiError,
  fetchCloseReadiness,
  fetchCompany,
  type CloseReadinessResult,
  type CompanySummary,
} from './api';
import { mapWithConcurrency } from './portfolio';

export type CloseReadinessAccess =
  | 'available'
  | 'restricted'
  | 'revoked'
  | 'unavailable';

export type CloseReadinessSnapshot = {
  company: CompanySummary;
  access: CloseReadinessAccess;
  result: CloseReadinessResult | null;
};

type CloseReadinessClient = {
  fetchCompany: typeof fetchCompany;
  fetchCloseReadiness: typeof fetchCloseReadiness;
};

const CLIENT: CloseReadinessClient = { fetchCompany, fetchCloseReadiness };

export function selectCloseReadinessCompanies(
  companies: readonly CompanySummary[],
  requested: string | string[] | undefined,
): CompanySummary[] {
  if (typeof requested !== 'string' || requested === 'todas') return [...companies];
  const selected = companies.find((company) => company.company_id === requested);
  // Un identificador no autorizado no funciona como oraculo: vuelve a la vista
  // de todas las empresas que ya estaban en la sesion.
  return selected ? [selected] : [...companies];
}

export async function loadCloseReadinessCompany(
  token: string,
  company: CompanySummary,
  client: CloseReadinessClient = CLIENT,
): Promise<CloseReadinessSnapshot> {
  let detail;
  try {
    detail = await client.fetchCompany(token, company.company_id);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) throw error;
    return {
      company,
      access: error instanceof ApiError && [403, 404].includes(error.status)
        ? 'revoked' : 'unavailable',
      result: null,
    };
  }
  if (!detail.permissions.includes('report.read')) {
    return { company, access: 'restricted', result: null };
  }
  try {
    return {
      company,
      access: 'available',
      result: await client.fetchCloseReadiness(token, company.company_id, 12),
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) throw error;
    return {
      company,
      access: error instanceof ApiError && [403, 404].includes(error.status)
        ? 'restricted' : 'unavailable',
      result: null,
    };
  }
}

export function loadCloseReadinessCenter(
  token: string,
  companies: readonly CompanySummary[],
): Promise<CloseReadinessSnapshot[]> {
  return mapWithConcurrency(companies, 3, (company) =>
    loadCloseReadinessCompany(token, company));
}

export function closePeriodKey(start: string, end: string): string {
  return `${start}:${end}`;
}

export function availableClosePeriods(
  snapshots: readonly CloseReadinessSnapshot[],
): Array<{ key: string; start: string; end: string }> {
  const periods = new Map<string, { key: string; start: string; end: string }>();
  for (const { result } of snapshots) {
    for (const period of result?.items ?? []) {
      const key = closePeriodKey(period.period_start, period.period_end);
      periods.set(key, { key, start: period.period_start, end: period.period_end });
    }
  }
  return [...periods.values()].sort((left, right) =>
    right.end.localeCompare(left.end) || right.start.localeCompare(left.start));
}

export function selectClosePeriod(
  available: readonly { key: string }[],
  requested: string | string[] | undefined,
): string {
  return typeof requested === 'string'
    && available.some((period) => period.key === requested)
    ? requested : 'todos';
}

export function filterCloseReadinessPeriod(
  snapshots: readonly CloseReadinessSnapshot[],
  selected: string,
): CloseReadinessSnapshot[] {
  if (selected === 'todos') return [...snapshots];
  return snapshots.map((snapshot) => {
    if (!snapshot.result) return snapshot;
    const items = snapshot.result.items.filter((period) =>
      closePeriodKey(period.period_start, period.period_end) === selected);
    return {
      ...snapshot,
      result: {
        ...snapshot.result,
        items,
        period_count: items.length,
        blocked_period_count: items.length,
        source_count: items.reduce((total, period) => total + period.source_count, 0),
      },
    };
  });
}

export function aggregateCloseReadinessCounts(
  snapshots: readonly CloseReadinessSnapshot[],
): { periods: number; blockedPeriods: number; sources: number;
     openReviews: number; highAlerts: number; pendingCorrections: number } {
  const total = {
    periods: 0,
    blockedPeriods: 0,
    sources: 0,
    openReviews: 0,
    highAlerts: 0,
    pendingCorrections: 0,
  };
  for (const { result } of snapshots) {
    if (!result) continue;
    total.periods += result.period_count;
    total.blockedPeriods += result.blocked_period_count;
    total.sources += result.source_count;
    for (const period of result.items) {
      const controls = new Map(period.controls.map((control) => [control.code, control]));
      total.openReviews += controls.get('reconciliation_reviews')?.count ?? 0;
      total.highAlerts += controls.get('quality_alerts')?.count ?? 0;
      total.pendingCorrections += controls.get('pending_corrections')?.count ?? 0;
    }
  }
  return total;
}

export function formatClosePeriod(start: string, end: string): string {
  const formatter = new Intl.DateTimeFormat('es-CO', {
    day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC',
  });
  return `${formatter.format(new Date(`${start}T00:00:00Z`))} — ${formatter.format(
    new Date(`${end}T00:00:00Z`),
  )}`;
}

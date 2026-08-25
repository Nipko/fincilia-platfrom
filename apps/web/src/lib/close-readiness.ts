import 'server-only';

import {
  ApiError,
  fetchCloseReadiness,
  fetchCompany,
  fetchStatementLineage,
  type CloseReadinessResult,
  type CompanySummary,
  type StatementLineage,
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
  statementLineages: Record<string, StatementLineageSnapshot>;
};

export type StatementLineageSnapshot = {
  access: 'available' | 'restricted' | 'unavailable';
  result: StatementLineage | null;
};

type CloseReadinessClient = {
  fetchCompany: typeof fetchCompany;
  fetchCloseReadiness: typeof fetchCloseReadiness;
  fetchStatementLineage: typeof fetchStatementLineage;
};

const CLIENT: CloseReadinessClient = {
  fetchCompany, fetchCloseReadiness, fetchStatementLineage,
};

function statementIds(result: CloseReadinessResult): string[] {
  return [...new Set(result.items.flatMap((period) =>
    period.account_reconciliations.flatMap((account) =>
      account.statement_id ? [account.statement_id] : [])))];
}

async function loadStatementLineages(
  token: string,
  companyId: string,
  result: CloseReadinessResult,
  allowed: boolean,
  client: CloseReadinessClient,
): Promise<Record<string, StatementLineageSnapshot>> {
  const ids = statementIds(result);
  if (!allowed) {
    return Object.fromEntries(ids.map((id) => [id, { access: 'restricted', result: null }]));
  }
  const entries = await mapWithConcurrency(ids, 3, async (id) => {
    try {
      return [id, {
        access: 'available',
        result: await client.fetchStatementLineage(token, companyId, id),
      }] as const;
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) throw error;
      return [id, {
        access: error instanceof ApiError && [403, 404].includes(error.status)
          ? 'restricted' : 'unavailable',
        result: null,
      }] as const;
    }
  });
  return Object.fromEntries(entries);
}

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
      statementLineages: {},
    };
  }
  if (!detail.permissions.includes('report.read')) {
    return { company, access: 'restricted', result: null, statementLineages: {} };
  }
  try {
    const result = await client.fetchCloseReadiness(token, company.company_id, 12);
    return {
      company,
      access: 'available',
      result,
      statementLineages: await loadStatementLineages(
        token, company.company_id, result,
        detail.permissions.includes('movement.read'), client),
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) throw error;
    return {
      company,
      access: error instanceof ApiError && [403, 404].includes(error.status)
        ? 'restricted' : 'unavailable',
      result: null,
      statementLineages: {},
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
        blocked_period_count: items.filter((item) => item.status === 'blocked').length,
        review_ready_period_count: items.filter(
          (item) => item.status === 'ready_for_review').length,
        source_count: items.reduce((total, period) => total + period.source_count, 0),
      },
    };
  });
}

export function aggregateCloseReadinessCounts(
  snapshots: readonly CloseReadinessSnapshot[],
): { periods: number; blockedPeriods: number; sources: number;
     reviewReadyPeriods: number; openReviews: number; highAlerts: number;
     pendingCorrections: number } {
  const total = {
    periods: 0,
    blockedPeriods: 0,
    sources: 0,
    reviewReadyPeriods: 0,
    openReviews: 0,
    highAlerts: 0,
    pendingCorrections: 0,
  };
  for (const { result } of snapshots) {
    if (!result) continue;
    total.periods += result.period_count;
    total.blockedPeriods += result.blocked_period_count;
    total.sources += result.source_count;
    total.reviewReadyPeriods += result.review_ready_period_count;
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

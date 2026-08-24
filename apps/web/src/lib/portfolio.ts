import 'server-only';

import {
  ApiError,
  fetchCompany,
  fetchDatasets,
  fetchDocuments,
  fetchExpectations,
  type ArtifactSummary,
  type CompanyDetail,
  type CompanySummary,
  type DatasetSummary,
  type Expectation,
} from './api';

export type Metric<T> =
  | { state: 'available'; value: T }
  | { state: 'restricted' }
  | { state: 'unavailable' };

type AvailableMetric<T> = { state: 'available'; value: T };

export type PortfolioSnapshot = {
  company: CompanySummary;
  access: 'available' | 'revoked' | 'unavailable';
  documents: Metric<{ visible: number; quarantine: number }>;
  datasets: Metric<{
    visible: number;
    pendingReview: number;
    partial: number;
    published: number;
  }>;
  expectations: Metric<{ overdue: number; dueSoon: number; pending: number }>;
};

type PortfolioClient = {
  fetchCompany: typeof fetchCompany;
  fetchDocuments: typeof fetchDocuments;
  fetchDatasets: typeof fetchDatasets;
  fetchExpectations: typeof fetchExpectations;
};

const DEFAULT_CLIENT: PortfolioClient = {
  fetchCompany,
  fetchDocuments,
  fetchDatasets,
  fetchExpectations,
};

const restricted = <T>(): Metric<T> => ({ state: 'restricted' });
const unavailable = <T>(): Metric<T> => ({ state: 'unavailable' });

function addUtcDays(isoDate: string, days: number): string {
  const [year, month, day] = isoDate.split('-').map(Number);
  if (!year || !month || !day) {
    return isoDate;
  }
  const date = new Date(Date.UTC(year, month - 1, day + days));
  return date.toISOString().slice(0, 10);
}

export function summarizeDocuments(
  documents: ArtifactSummary[],
): AvailableMetric<{ visible: number; quarantine: number }> {
  return {
    state: 'available',
    value: {
      visible: documents.length,
      quarantine: documents.filter((item) => item.zone === 'quarantine').length,
    },
  };
}

export function summarizeDatasets(
  datasets: DatasetSummary[],
): AvailableMetric<{
  visible: number;
  pendingReview: number;
  partial: number;
  published: number;
}> {
  return {
    state: 'available',
    value: {
      visible: datasets.length,
      pendingReview: datasets.filter((item) => item.state === 'validated').length,
      partial: datasets.filter((item) => item.state === 'staging').length,
      published: datasets.filter((item) => item.state === 'published').length,
    },
  };
}

export function summarizeExpectations(
  expectations: Expectation[],
  today: string,
): AvailableMetric<{ overdue: number; dueSoon: number; pending: number }> {
  const soonThrough = addUtcDays(today, 7);
  const pending = expectations.filter((item) => item.stored_state === 'pending');
  return {
    state: 'available',
    value: {
      overdue: pending.filter((item) => item.days_late > 0).length,
      dueSoon: pending.filter(
        (item) =>
          item.days_late === 0 && item.due_on >= today && item.due_on <= soonThrough,
      ).length,
      pending: pending.length,
    },
  };
}

async function metricCall<T>(operation: Promise<T>): Promise<Metric<T>> {
  try {
    return { state: 'available', value: await operation };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      throw error;
    }
    if (error instanceof ApiError && error.status === 403) {
      return restricted();
    }
    return unavailable();
  }
}

/** Carga una empresa sin convertir permiso ausente o revocado en conteo cero. */
export async function loadCompanySnapshot(
  token: string,
  company: CompanySummary,
  today: string,
  client: PortfolioClient = DEFAULT_CLIENT,
): Promise<PortfolioSnapshot> {
  let detail: CompanyDetail;
  try {
    detail = await client.fetchCompany(token, company.company_id);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      throw error;
    }
    const access =
      error instanceof ApiError && (error.status === 403 || error.status === 404)
        ? 'revoked'
        : 'unavailable';
    return {
      company,
      access,
      documents: access === 'revoked' ? restricted() : unavailable(),
      datasets: access === 'revoked' ? restricted() : unavailable(),
      expectations: access === 'revoked' ? restricted() : unavailable(),
    };
  }

  const documentPermission = detail.permissions.includes('document.read');
  const movementPermission = detail.permissions.includes('movement.read');
  const [documentsResult, expectationsResult, datasetsResult] = await Promise.all([
    documentPermission
      ? metricCall(client.fetchDocuments(token, company.company_id))
      : Promise.resolve(restricted<ArtifactSummary[]>()),
    documentPermission
      ? metricCall(client.fetchExpectations(token, company.company_id))
      : Promise.resolve(restricted<Expectation[]>()),
    movementPermission
      ? metricCall(client.fetchDatasets(token, company.company_id))
      : Promise.resolve(restricted<DatasetSummary[]>()),
  ]);

  return {
    company,
    access: 'available',
    documents:
      documentsResult.state === 'available'
        ? summarizeDocuments(documentsResult.value)
        : documentsResult,
    datasets:
      datasetsResult.state === 'available'
        ? summarizeDatasets(datasetsResult.value)
        : datasetsResult,
    expectations:
      expectationsResult.state === 'available'
        ? summarizeExpectations(expectationsResult.value, today)
        : expectationsResult,
  };
}

/** Pool pequeno: una firma con muchas empresas no dispara una rafaga sin limite. */
export async function mapWithConcurrency<T, R>(
  items: readonly T[],
  limit: number,
  operation: (item: T, index: number) => Promise<R>,
): Promise<R[]> {
  const safeLimit = Math.max(1, Math.min(Math.trunc(limit), 8));
  const results = new Array<R>(items.length);
  let next = 0;
  const worker = async () => {
    while (next < items.length) {
      const index = next;
      next += 1;
      const item = items[index];
      if (item !== undefined) {
        results[index] = await operation(item, index);
      }
    }
  };
  await Promise.all(
    Array.from({ length: Math.min(safeLimit, items.length) }, () => worker()),
  );
  return results;
}

export function loadPortfolioSnapshots(
  token: string,
  companies: readonly CompanySummary[],
  today: string,
): Promise<PortfolioSnapshot[]> {
  return mapWithConcurrency(companies, 4, (company) =>
    loadCompanySnapshot(token, company, today),
  );
}

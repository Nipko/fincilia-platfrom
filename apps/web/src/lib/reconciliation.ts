export const CANDIDATE_PAGE_SIZE = 25;
export const MAX_CANDIDATE_PAGE = 400;

type QueryValue = string | string[] | undefined;

export type ReconciliationSelection = {
  requested: boolean;
  valid: boolean;
  leftDatasetId: string;
  rightDatasetId: string;
  maxDays: number;
  page: number;
};

function single(value: QueryValue): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed || null;
}

function boundedInteger(value: QueryValue, fallback: number, min: number,
                        max: number): number | null {
  if (value === undefined) return fallback;
  const raw = single(value);
  if (raw === null || !/^\d+$/.test(raw)) return null;
  const parsed = Number(raw);
  return Number.isSafeInteger(parsed) && parsed >= min && parsed <= max
    ? parsed
    : null;
}

export function selectReconciliation(
  query: Record<string, QueryValue>,
  authorisedDatasetIds: readonly string[],
): ReconciliationSelection {
  const left = single(query.izquierda);
  const right = single(query.derecha);
  const requested = query.izquierda !== undefined || query.derecha !== undefined;
  const maxDays = boundedInteger(query.ventana, 3, 0, 31);
  const page = boundedInteger(query.pagina, 0, 0, MAX_CANDIDATE_PAGE);
  const authorised = new Set(authorisedDatasetIds);
  const valid = Boolean(
    requested && left && right && left !== right && authorised.has(left)
      && authorised.has(right) && maxDays !== null && page !== null,
  );
  return {
    requested,
    valid,
    leftDatasetId: left ?? '',
    rightDatasetId: right ?? '',
    maxDays: maxDays ?? 3,
    page: page ?? 0,
  };
}

export function reconciliationUrl(
  companyId: string,
  selection: Pick<ReconciliationSelection,
    'leftDatasetId' | 'rightDatasetId' | 'maxDays' | 'page'>,
): string {
  const params = new URLSearchParams({
    izquierda: selection.leftDatasetId,
    derecha: selection.rightDatasetId,
    ventana: String(selection.maxDays),
    pagina: String(selection.page),
  });
  return `/empresas/${encodeURIComponent(companyId)}/conciliacion?${params.toString()}`;
}

export function formatExactMoney(amount: string, currency: string): string {
  const match = /^(\d+)(?:\.(\d+))?$/.exec(amount);
  if (!match) return `${amount} ${currency}`;
  const whole = (match[1] ?? '').replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  const fraction = (match[2] ?? '').replace(/0+$/, '');
  return `${whole}${fraction ? `,${fraction}` : ''} ${currency}`;
}

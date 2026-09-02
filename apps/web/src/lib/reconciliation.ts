export const CANDIDATE_PAGE_SIZE = 25;
export const MAX_CANDIDATE_PAGE = 400;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

type QueryValue = string | string[] | undefined;
export type ReferenceMode = 'all' | 'matching' | 'different';
const REFERENCE_MODES = new Set<ReferenceMode>(['all', 'matching', 'different']);

export type ReconciliationSelection = {
  requested: boolean;
  valid: boolean;
  leftDatasetId: string;
  rightDatasetId: string;
  maxDays: number;
  referenceMode: ReferenceMode;
  page: number;
};

export type ReconciliationReviewReference = {
  requested: boolean;
  valid: boolean;
  candidateId: string;
};

export type ReviewInboxReturn = {
  requested: boolean;
  valid: boolean;
  filter: 'abiertas' | 'confirmadas' | 'rechazadas' | 'todas';
  companyId: string | null;
  page: number;
};

const REVIEW_RETURN_FILTERS = new Set<ReviewInboxReturn['filter']>([
  'abiertas', 'confirmadas', 'rechazadas', 'todas',
]);
const MAX_REVIEW_RETURN_PAGE = 200;

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
  const requested = query.izquierda !== undefined || query.derecha !== undefined
    || query.referencia !== undefined;
  const maxDays = boundedInteger(query.ventana, 3, 0, 31);
  const reference = single(query.referencia) ?? 'all';
  const referenceMode = REFERENCE_MODES.has(reference as ReferenceMode)
    ? reference as ReferenceMode
    : null;
  const page = boundedInteger(query.pagina, 0, 0, MAX_CANDIDATE_PAGE);
  const authorised = new Set(authorisedDatasetIds);
  const valid = Boolean(
    requested && left && right && left !== right && authorised.has(left)
      && authorised.has(right) && maxDays !== null && referenceMode !== null
      && page !== null,
  );
  return {
    requested,
    valid,
    leftDatasetId: left ?? '',
    rightDatasetId: right ?? '',
    maxDays: maxDays ?? 3,
    referenceMode: referenceMode ?? 'all',
    page: page ?? 0,
  };
}

export function reconciliationUrl(
  companyId: string,
  selection: Pick<ReconciliationSelection,
    'leftDatasetId' | 'rightDatasetId' | 'maxDays' | 'referenceMode' | 'page'>,
): string {
  const params = new URLSearchParams({
    izquierda: selection.leftDatasetId,
    derecha: selection.rightDatasetId,
    ventana: String(selection.maxDays),
    referencia: selection.referenceMode,
    pagina: String(selection.page),
  });
  return `/empresas/${encodeURIComponent(companyId)}/conciliacion?${params.toString()}`;
}

export function selectReconciliationReview(
  query: Record<string, QueryValue>,
): ReconciliationReviewReference {
  const candidateId = single(query.revision) ?? '';
  return {
    requested: query.revision !== undefined,
    valid: UUID_PATTERN.test(candidateId),
    candidateId,
  };
}

export function selectReviewInboxReturn(
  query: Record<string, QueryValue>,
  currentCompanyId: string,
): ReviewInboxReturn {
  const requested = query.bandeja_estado !== undefined
    || query.bandeja_empresa !== undefined || query.bandeja_pagina !== undefined;
  const rawFilter = single(query.bandeja_estado);
  const rawCompany = single(query.bandeja_empresa);
  const page = boundedInteger(
    query.bandeja_pagina, 0, 0, MAX_REVIEW_RETURN_PAGE,
  );
  const filter = REVIEW_RETURN_FILTERS.has(rawFilter as ReviewInboxReturn['filter'])
    ? rawFilter as ReviewInboxReturn['filter']
    : null;
  const companyId = rawCompany === 'todas'
    ? null
    : rawCompany === currentCompanyId ? currentCompanyId : undefined;
  const valid = Boolean(
    requested && filter && companyId !== undefined && page !== null
      && (companyId !== null || page === 0),
  );
  return {
    requested,
    valid,
    filter: filter ?? 'abiertas',
    companyId: companyId ?? null,
    page: valid ? page ?? 0 : 0,
  };
}

export function reviewInboxReturnUrl(selection: Pick<ReviewInboxReturn,
  'filter' | 'companyId' | 'page'>): string {
  const params = new URLSearchParams({
    estado: selection.filter,
    empresa: selection.companyId ?? 'todas',
  });
  if (selection.companyId && selection.page > 0) {
    params.set('pagina', String(selection.page));
  }
  return `/revisiones?${params.toString()}`;
}

export function reconciliationReviewUrl(
  companyId: string,
  selection: Pick<ReconciliationSelection,
    'leftDatasetId' | 'rightDatasetId' | 'maxDays' | 'referenceMode' | 'page'>,
  candidateId: string,
  inboxReturn?: Pick<ReviewInboxReturn, 'filter' | 'companyId' | 'page'>,
): string {
  const params = new URLSearchParams({ revision: candidateId });
  if (inboxReturn) {
    params.set('bandeja_estado', inboxReturn.filter);
    params.set('bandeja_empresa', inboxReturn.companyId ?? 'todas');
    if (inboxReturn.companyId && inboxReturn.page > 0) {
      params.set('bandeja_pagina', String(inboxReturn.page));
    }
  }
  return `${reconciliationUrl(companyId, selection)}&${params.toString()}` +
    `#revision-${encodeURIComponent(candidateId)}`;
}

export function formatExactMoney(amount: string, currency: string): string {
  const match = /^(-?)(\d+)(?:\.(\d+))?$/.exec(amount);
  if (!match) return `${amount} ${currency}`;
  const whole = (match[2] ?? '').replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  const fraction = (match[3] ?? '').replace(/0+$/, '');
  return `${match[1]}${whole}${fraction ? `,${fraction}` : ''} ${currency}`;
}

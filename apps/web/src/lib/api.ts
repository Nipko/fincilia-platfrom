import 'server-only';

import { apiUrl } from './server-config';

/**
 * Cliente de la API de Fincilia. **Solo servidor.**
 *
 * El navegador nunca ve el token: entra en una cookie `httpOnly` y sale de ella
 * dentro del proceso de Next, que es quien llama a la API. Un cliente que
 * guardara el token en `localStorage` lo pondria al alcance de cualquier script
 * de la pagina, y la interfaz dejaria de ser solo una vista.
 *
 * Aqui no se decide nada: si la API responde 403, la web ensena que no hay
 * acceso. No hay una segunda copia de la matriz de permisos que pueda quedar
 * desincronizada de la del servidor.
 */

export type CompanySummary = {
  company_id: string;
  legal_name: string;
  country_code: string;
  status: string;
  roles: string[];
};

export type CompanyDetail = CompanySummary & {
  firm_id: string;
  engagement_id: string | null;
  authorization_version: number;
  permissions: string[];
};

export type AuditEvent = {
  audit_event_id: string;
  action: string;
  resource_kind: string;
  resource_ref: string;
  outcome: string;
  occurred_at: string;
  detail: Record<string, unknown>;
  subject_id: string | null;
  actor_name: string;
};

export type AuditPage = {
  items: AuditEvent[];
  has_more: boolean;
  next_cursor: string | null;
  limit: number;
};

export type AuditFilters = {
  action?: string;
  outcome?: 'allowed' | 'denied' | 'error';
  resourceKind?: string;
  cursor?: string;
  limit?: number;
};

export type Me = {
  subject_id: string;
  display_name: string;
  session_expires_at: number;
  companies: CompanySummary[];
};

export type Session = {
  token: string;
  expires_at: number;
  subject_id: string;
  display_name: string;
};

export type ManagedFirm = {
  firm_id: string;
  legal_name: string;
  firm_role: string;
};

export type InitialCompanySetup = {
  account_family: string;
  account_name: string;
  account_identifier: string;
  currency_code: string;
  source_family: string;
  source_name: string;
  purpose_code: string;
  timezone: string;
  anchor_date: string;
  due_day_offset: number;
  grace_days: number;
};

export type CompanyProvisionInput = {
  firm_id: string;
  legal_name: string;
  country_code: string;
  tax_identifier: string;
  setup: InitialCompanySetup | null;
};

export type CompanyProvisionResult = CompanyDetail & {
  account_id: string | null;
  source_id: string | null;
  link_id: string | null;
  cycle_id: string | null;
  expectations_created: number;
  replayed: boolean;
  refreshed_session: Session;
};

/** Fallo con el codigo que devolvio la API, para poder distinguir 401 de 403. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;

  constructor(status: number, message: string, code: string | null = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

const REQUEST_TIMEOUT_MS = 8000;

async function request<T>(
  path: string,
  init: RequestInit & { token?: string } = {},
): Promise<T> {
  const { token, headers, ...rest } = init;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(apiUrl(path), {
      ...rest,
      // Nada de la API se cachea: una lista de empresas cacheada es la lista de
      // otra persona en cuanto dos usuarios comparten el proceso.
      cache: 'no-store',
      signal: controller.signal,
      headers: {
        accept: 'application/json',
        ...(token ? { authorization: `Bearer ${token}` } : {}),
        ...headers,
      },
    });
    if (!response.ok) {
      // El detalle de la API ya esta escrito para no filtrar datos; se pasa tal
      // cual y no se enriquece con nada que el servidor haya decidido callar.
      let detail = 'la peticion no se pudo completar';
      let code: string | null = null;
      try {
        const problem = (await response.json()) as { detail?: unknown; type?: unknown };
        if (typeof problem.detail === 'string') {
          detail = problem.detail;
        }
        if (typeof problem.type === 'string') {
          code = problem.type.split('/').filter(Boolean).at(-1) ?? null;
        }
      } catch {
        /* un cuerpo ilegible no cambia el codigo de estado */
      }
      throw new ApiError(response.status, detail, code);
    }
    // El deadline cubre tambien el cuerpo. Recibir headers no basta: un servidor
    // que entregue JSON gota a gota no puede colgar una pantalla indefinidamente.
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(503, 'no se pudo contactar con la API');
  } finally {
    clearTimeout(timer);
  }
}

export function signIn(username: string, secret: string): Promise<Session> {
  return request<Session>('/api/v1/auth/session', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ username, secret }),
  });
}

export function fetchMe(token: string): Promise<Me> {
  return request<Me>('/api/v1/me', { token });
}

export function fetchCompany(token: string, companyId: string): Promise<CompanyDetail> {
  return request<CompanyDetail>(`/api/v1/companies/${encodeURIComponent(companyId)}`, {
    token,
  });
}

export function fetchAudit(token: string, companyId: string): Promise<AuditEvent[]> {
  return request<AuditEvent[]>(
    `/api/v1/companies/${encodeURIComponent(companyId)}/audit?limit=25`,
    { token },
  );
}

export type PromotionDecision = {
  decision: string;
  reason_code: string;
  scanner_release?: string;
  media_type?: string;
  internal_type?: string;
  findings?: { kind: string; location: string; detail: string }[];
  raw_object_key?: string | null;
  decided_at?: string;
};

export type ArtifactSummary = {
  artifact_id: string;
  filename: string;
  byte_size: number;
  content_sha256: string;
  media_type: string;
  zone: string;
  status: string;
  findings: { kind: string; location: string; detail: string }[];
  uploaded_at: string;
  already_present: boolean;
  promotion: PromotionDecision | null;
};

export function fetchDocuments(
  token: string,
  companyId: string,
): Promise<ArtifactSummary[]> {
  return request<ArtifactSummary[]>(
    `/api/v1/companies/${encodeURIComponent(companyId)}/documents?limit=50`,
    { token },
  );
}

export type ProcessingRun = {
  run_id: string;
  kind: string;
  status: string;
  attempt: number;
  queued_at: string;
  finished_at: string | null;
  result: Record<string, unknown>;
  error_code: string | null;
};

export type SpreadsheetSheet = {
  sheet_identity: string;
  name: string;
  ordinal: number;
  state: string;
};

export type SpreadsheetSelection = {
  selection_id: string;
  workbook_identity: string;
  sheet_identity: string;
  sheet_name: string;
  sheet_ordinal: number;
  selected_by: string;
  selected_at: string;
};

export type SpreadsheetWorkspace = {
  workbook_identity: string;
  sheet_count: number;
  sheets: SpreadsheetSheet[];
  requires_selection: boolean;
  selection: SpreadsheetSelection | null;
};

export type ArtifactDetail = ArtifactSummary & {
  runs: ProcessingRun[];
  spreadsheet: SpreadsheetWorkspace | null;
};

export type ColumnProfile = {
  index: number;
  header: string;
  non_empty: number;
  empty: number;
  min_length: number;
  max_length: number;
  inferred_type: string;
  type_confidence: number;
  ambiguous: boolean;
};

export type TableProfile = {
  technical_format?: string;
  encoding: string;
  delimiter: string;
  sheet_name?: string;
  sheet_ordinal?: number;
  has_header: boolean;
  row_count: number;
  column_count: number;
  ragged_rows: number;
  truncated: boolean;
  needs_decision: string[];
  columns: ColumnProfile[];
};

export function fetchDocument(
  token: string,
  companyId: string,
  artifactId: string,
): Promise<ArtifactDetail> {
  const company = encodeURIComponent(companyId);
  const artifact = encodeURIComponent(artifactId);
  return request<ArtifactDetail>(
    `/api/v1/companies/${company}/documents/${artifact}`,
    { token },
  );
}

export function selectSpreadsheetSheet(
  token: string,
  companyId: string,
  artifactId: string,
  sheetIdentity: string,
): Promise<SpreadsheetSelection & { created: boolean }> {
  const company = encodeURIComponent(companyId);
  const artifact = encodeURIComponent(artifactId);
  return request<SpreadsheetSelection & { created: boolean }>(
    `/api/v1/companies/${company}/documents/${artifact}/spreadsheet-selection`,
    {
      method: 'POST',
      token,
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ sheet_identity: sheetIdentity }),
    },
  );
}

// --------------------------------------------------------------------------- //
// Mapeo, dataset canonico y movimientos (FNC-P3)
// --------------------------------------------------------------------------- //

/** Coordenada exacta de una fila o de una celda dentro del artefacto. */
export type OriginLocator = {
  locator_kind: string;
  artifact_sha256: string;
  record_ordinal: number;
  byte_start: number;
  byte_end: number;
  field_count: number;
  field_ordinal?: number;
};

export type PreviewRow = {
  record_ordinal: number;
  values: string[];
  locator: OriginLocator;
};

export type PreviewPage = {
  artifact_id: string;
  run_id: string;
  header: string[];
  header_row: number;
  first_data_row: number;
  columns: ColumnProfile[];
  total_records: number;
  offset: number;
  limit: number;
  truncated: boolean;
  truncation_reason: string | null;
  rows: PreviewRow[];
};

/** Lo que impide publicar, con la decision que lo levantaria si la hay. */
export type Blocker = {
  code: string;
  location: string;
  detail: string;
  ambiguity_kind: string;
  subject_ref: string;
  expected_value: string;
  resolvable: string;
};

export type MappingDecision = {
  decision_id: string;
  ambiguity_kind: string;
  subject_ref: string;
  resolved_value: string;
  rationale: string;
  decided_by: string;
  decided_at: string;
};

export type MappingVersion = {
  mapping_version_id: string;
  mapping_id: string;
  version_number: number;
  artifact_id: string;
  definition: Record<string, unknown>;
  definition_digest: string;
  source_schema_digest: string;
  state: string;
  created_by: string;
  created_at: string;
  validated_by: string | null;
  display_name: string;
  data_source_id: string;
};

export type UnaccountedColumn = {
  index: number;
  header: string;
  inferred_type: string;
};

export type MappingDetail = MappingVersion & {
  decisions: MappingDecision[];
  blockers: Blocker[];
  unaccounted_columns: UnaccountedColumn[];
  columns: ColumnProfile[];
};

export type MappingSummary = {
  mapping_version_id: string;
  mapping_id: string;
  version_number: number;
  artifact_id: string;
  state: string;
  display_name: string;
  created_at: string;
};

export type DatasetSummary = {
  dataset_version_id: string;
  artifact_id: string;
  state: string;
  movement_count: number;
  rejected_count: number;
  prepared_at: string;
  published_at: string | null;
};

export type DatasetDetail = DatasetSummary & {
  processing_run_id: string;
  mapping_version_id: string;
  completeness_state: string;
  lineage_state: string;
  record_count: number;
  expected_record_count?: number;
  prepared_by: string;
  validated_by: string | null;
  published_by: string | null;
  rejected_reason: string | null;
  canonical_schema_version: string;
  engine_release: string;
  can_publish: boolean;
  publish_blockers: { code: string; detail: string }[];
  manifest: {
    reproduction_key: string;
    reproducible: boolean;
    locale: string;
    timezone: string;
    deterministic_config: Record<string, unknown>;
  } | null;
};

export type Movement = {
  movement_id: string;
  amount: string;
  currency: string;
  direction: string;
  description: string;
  reference: string | null;
  occurred_on: string;
  posted_on: string | null;
  value_date: string | null;
  accounting_date: string | null;
  state: string;
  kind: string;
  record_ordinal: number;
};

export type CandidateMovement = Pick<
  Movement,
  | 'movement_id'
  | 'amount'
  | 'currency'
  | 'direction'
  | 'description'
  | 'reference'
  | 'occurred_on'
  | 'state'
  | 'record_ordinal'
>;

export type ReconciliationCandidate = {
  left: CandidateMovement;
  right: CandidateMovement;
  date_distance_days: number;
  signals: string[];
};

export type CandidateDataset = {
  dataset_version_id: string;
  state: string;
  completeness_state: string;
  lineage_state: string;
  movement_count: number;
};

export type CandidatePage = {
  mode: 'candidate_only';
  proves_balance_reconciliation: false;
  rules: string[];
  reference_role: 'explanatory_order_only';
  max_days: number;
  offset: number;
  limit: number;
  truncated: boolean;
  left_dataset: CandidateDataset;
  right_dataset: CandidateDataset;
  candidates: ReconciliationCandidate[];
};

export type MatchDecision = {
  decision_id: string;
  decision: 'confirmed' | 'rejected';
  reason_code: string;
  decided_by: string;
  decided_by_name: string;
  decided_at: string;
};

export type MatchReview = {
  candidate_id: string;
  left_movement_id: string;
  right_movement_id: string;
  left_dataset_id: string;
  right_dataset_id: string;
  confirmation_conflict: boolean;
  rule_version: string;
  signals: string[];
  date_window_days: number;
  date_distance_days: number;
  proposed_by: string;
  proposed_by_name: string;
  proposed_at: string;
  status: 'open' | 'confirmed' | 'rejected';
  decision: MatchDecision | null;
  financial_effect: 'none';
  proves_balance_reconciliation: false;
  replayed?: boolean;
  created?: boolean;
};

export type MatchGroupProposal = {
  group_candidate_id: string;
  anchor_dataset_id: string;
  related_dataset_id: string;
  anchor: CandidateMovement;
  related: CandidateMovement[];
  related_movement_count: number;
  related_total: string;
  difference: string;
  currency: string;
  rule_version: string;
  proposed_by: string;
  proposed_by_name: string;
  proposed_at: string;
  view_relation: 'one_to_many' | 'many_to_one';
  status: 'draft';
  financial_effect: 'none';
  proves_balance_reconciliation: false;
  can_confirm: false;
  replayed?: boolean;
  created?: boolean;
};

export type ReviewQueueStatus = 'open' | 'confirmed' | 'rejected' | 'all';

export type ReviewQueuePage = {
  status: ReviewQueueStatus;
  offset: number;
  limit: number;
  truncated: boolean;
  items: MatchReview[];
  financial_effect: 'none';
  proves_balance_reconciliation: false;
};

/** Una etapa logica del camino de un campo publicado. */
export type LineageStage = {
  canonical_field: string;
  step_ordinal: number;
  stage: string;
  operation: string;
  input_semantic_type: string;
  output_semantic_type: string;
  transform_ref: string | null;
  configuration_digest: string;
  parser_version: string;
  rule_version: string;
  source_column: number | null;
  identity: Record<string, unknown>;
};

export type LineageStep = {
  field: string;
  stages: LineageStage[];
  cell: OriginLocator;
  transform: string;
  value_digest: string;
  operation: string;
};

export type MovementDetail = Movement & {
  dataset_version_id: string;
  dataset_state: string;
  engine_release: string;
  origin: { filename: string; locator: OriginLocator; values: string[] };
  lineage: LineageStep[];
  lineage_complete: boolean;
  lineage_reason?: string;
};

export type MappingDefinition = {
  columns: Record<string, number>;
  date_format: string;
  decimal_format: string;
  currency: string;
  direction_mode: string;
  header_row: number;
  first_data_row: number;
  last_data_row: number | null;
  ignored_columns: number[];
};

export type MappingPreviewMovement = {
  row_number: number;
  occurred_on: string;
  description: string;
  reference: string;
  amount: string;
  currency: string;
  direction: string;
  source_column: Record<string, number>;
};

export type MappingPreview = {
  header_row: number;
  first_data_row: number;
  last_data_row: number | null;
  range_record_count: number;
  sample_limit: number;
  sampled_count: number;
  sample_truncated: boolean;
  blockers: Blocker[];
  movements: MappingPreviewMovement[];
  rejections: { record_ordinal: number; code: string; detail: string }[];
};

export type MappingTemplate = {
  mapping_id: string;
  display_name: string;
  data_source_id: string;
  mapping_version_id: string;
  version_number: number;
  artifact_id: string;
  definition: MappingDefinition;
  definition_digest: string;
  source_schema_digest: string;
  state: string;
  created_at: string;
  compatible: boolean;
};

export function fetchPreview(
  token: string,
  companyId: string,
  artifactId: string,
  offset = 0,
  limit = 25,
): Promise<PreviewPage> {
  const company = encodeURIComponent(companyId);
  const artifact = encodeURIComponent(artifactId);
  return request<PreviewPage>(
    `/api/v1/companies/${company}/documents/${artifact}/preview` +
      `?offset=${Math.max(0, offset)}&limit=${Math.max(1, limit)}`,
    { token },
  );
}

export function fetchMappings(
  token: string,
  companyId: string,
  artifactId: string,
): Promise<MappingSummary[]> {
  const company = encodeURIComponent(companyId);
  const artifact = encodeURIComponent(artifactId);
  return request<MappingSummary[]>(
    `/api/v1/companies/${company}/mappings?artifact_id=${artifact}`,
    { token },
  );
}

export function fetchMapping(
  token: string,
  companyId: string,
  mappingVersionId: string,
): Promise<MappingDetail> {
  const company = encodeURIComponent(companyId);
  const version = encodeURIComponent(mappingVersionId);
  return request<MappingDetail>(`/api/v1/companies/${company}/mappings/${version}`, {
    token,
  });
}

export function createMapping(
  token: string,
  companyId: string,
  body: MappingDefinition & {
    artifact_id: string;
    data_source_id: string;
    display_name: string;
  },
): Promise<{ mapping_version_id: string; blockers: Blocker[] }> {
  return request(`/api/v1/companies/${encodeURIComponent(companyId)}/mappings`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
    token,
  });
}

export function previewMapping(
  token: string,
  companyId: string,
  artifactId: string,
  body: MappingDefinition,
): Promise<MappingPreview> {
  const company = encodeURIComponent(companyId);
  const artifact = encodeURIComponent(artifactId);
  return request<MappingPreview>(
    `/api/v1/companies/${company}/documents/${artifact}/mapping-preview?limit=10`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
      token,
    },
  );
}

export function fetchMappingTemplates(
  token: string,
  companyId: string,
  dataSourceId: string,
  artifactId: string,
): Promise<MappingTemplate[]> {
  const query = new URLSearchParams({
    data_source_id: dataSourceId,
    artifact_id: artifactId,
  });
  return request<MappingTemplate[]>(
    `/api/v1/companies/${encodeURIComponent(companyId)}/mapping-templates?${query}`,
    { token },
  );
}

export function createMappingVersion(
  token: string,
  companyId: string,
  mappingId: string,
  body: MappingDefinition & { artifact_id: string },
): Promise<{
  mapping_version_id: string;
  blockers: Blocker[];
  replayed: boolean;
}> {
  const company = encodeURIComponent(companyId);
  const mapping = encodeURIComponent(mappingId);
  return request<{
    mapping_version_id: string;
    blockers: Blocker[];
    replayed: boolean;
  }>(
    `/api/v1/companies/${company}/mapping-templates/${mapping}/versions`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
      token,
    },
  );
}

export function decideAmbiguity(
  token: string,
  companyId: string,
  mappingVersionId: string,
  body: {
    ambiguity_kind: string;
    subject_ref: string;
    resolved_value: string;
    rationale: string;
  },
): Promise<{ decision_id: string; created: boolean }> {
  const company = encodeURIComponent(companyId);
  const version = encodeURIComponent(mappingVersionId);
  return request(`/api/v1/companies/${company}/mappings/${version}/decisions`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
    token,
  });
}

export function validateMapping(
  token: string,
  companyId: string,
  mappingVersionId: string,
): Promise<MappingVersion> {
  const company = encodeURIComponent(companyId);
  const version = encodeURIComponent(mappingVersionId);
  return request<MappingVersion>(
    `/api/v1/companies/${company}/mappings/${version}/validate`,
    { method: 'POST', token },
  );
}

export function prepareDataset(
  token: string,
  companyId: string,
  body: {
    artifact_id: string;
    mapping_version_id: string;
    financial_account_id: string;
  },
): Promise<{
  dataset_version_id: string;
  state: string;
  movement_count: number;
  rejected_count: number;
  record_count: number;
  reused: boolean;
  rejections: { record_ordinal: number; code: string; detail: string }[];
}> {
  return request(`/api/v1/companies/${encodeURIComponent(companyId)}/datasets`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
    token,
  });
}

export function fetchDatasets(
  token: string,
  companyId: string,
  artifactId?: string,
): Promise<DatasetSummary[]> {
  const company = encodeURIComponent(companyId);
  const query = artifactId
    ? `?artifact_id=${encodeURIComponent(artifactId)}`
    : '';
  return request<DatasetSummary[]>(
    `/api/v1/companies/${company}/datasets${query}`,
    { token },
  );
}

export function fetchAuditPage(
  token: string,
  companyId: string,
  filters: AuditFilters = {},
): Promise<AuditPage> {
  const query = new URLSearchParams();
  query.set('limit', String(Math.max(1, Math.min(filters.limit ?? 25, 100))));
  if (filters.action) query.set('action', filters.action);
  if (filters.outcome) query.set('outcome', filters.outcome);
  if (filters.resourceKind) query.set('resource_kind', filters.resourceKind);
  if (filters.cursor) query.set('cursor', filters.cursor);
  return request<AuditPage>(
    `/api/v1/companies/${encodeURIComponent(companyId)}/audit/events?${query}`,
    { token },
  );
}

export function fetchManageableFirms(token: string): Promise<ManagedFirm[]> {
  return request<ManagedFirm[]>('/api/v1/firms/manageable', { token });
}

export function provisionCompany(
  token: string,
  input: CompanyProvisionInput,
  idempotencyKey: string,
): Promise<CompanyProvisionResult> {
  return request<CompanyProvisionResult>('/api/v1/companies', {
    token,
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'idempotency-key': idempotencyKey,
    },
    body: JSON.stringify(input),
  });
}

export type ReportRange = {
  days: 30 | 90 | 180 | 365;
  start: string;
  end: string;
  timezone: 'UTC';
};

export type ReportActivityPoint = {
  month: string;
  documents: number;
  datasets: number;
  movements: number;
};

export type ReportMoneyPoint = {
  month: string;
  currency: string;
  movement_count: number;
  inflow_amount: string;
  outflow_amount: string;
};

export type ReportMoneyTotal = Omit<ReportMoneyPoint, 'month'>;

export type ReportDataset = {
  dataset_version_id: string;
  artifact_id: string;
  state: string;
  completeness_state: string;
  lineage_state: string;
  record_count: number;
  movement_count: number;
  rejected_count: number;
  prepared_at: string;
};

export type OperationalReport = {
  range: ReportRange;
  summary: {
    documents: { total: number; accepted: number; quarantined: number; bytes: number };
    datasets: {
      total: number; draft: number; validated: number; published: number;
      rejected: number; records: number; movements: number; rejected_records: number;
      completeness_mismatch: number; completeness_unknown: number;
      lineage_invalidated: number;
    };
    reconciliation: {
      candidates: number; pending: number; confirmed: number; rejected: number;
    };
    quality: {
      signals: number; open: number; acknowledged: number; closed: number;
      active_high: number;
    };
  };
  activity_series: ReportActivityPoint[];
  money_totals: ReportMoneyTotal[];
  money_series: ReportMoneyPoint[];
  recent_datasets: ReportDataset[];
  notice: string;
};

export function fetchOperationalReport(
  token: string,
  companyId: string,
  days: 30 | 90 | 180 | 365,
  asOf?: string,
): Promise<OperationalReport> {
  const query = new URLSearchParams({ days: String(days) });
  if (asOf) query.set('as_of', asOf);
  return request<OperationalReport>(
    `/api/v1/companies/${encodeURIComponent(companyId)}/reports/operational?${query}`,
    { token },
  );
}

export function fetchDataset(
  token: string,
  companyId: string,
  datasetVersionId: string,
): Promise<DatasetDetail> {
  const company = encodeURIComponent(companyId);
  const dataset = encodeURIComponent(datasetVersionId);
  return request<DatasetDetail>(`/api/v1/companies/${company}/datasets/${dataset}`, {
    token,
  });
}

export function publishDataset(
  token: string,
  companyId: string,
  datasetVersionId: string,
): Promise<DatasetDetail> {
  const company = encodeURIComponent(companyId);
  const dataset = encodeURIComponent(datasetVersionId);
  return request<DatasetDetail>(
    `/api/v1/companies/${company}/datasets/${dataset}/publish`,
    { method: 'POST', token },
  );
}

export type RowOverrideSummary = {
  override_id: string;
  canonical_field: string;
  override_kind: string;
  base_step_ordinal: number;
  rule_version: string;
  reason_code: string;
  created_by: string;
  approved_by: string | null;
  engine_release_id: string;
  canonical_schema_version: string;
  needs_approval: boolean;
  approved: boolean;
};

export function fetchOverrides(
  token: string,
  companyId: string,
  datasetVersionId: string,
): Promise<RowOverrideSummary[]> {
  const company = encodeURIComponent(companyId);
  const dataset = encodeURIComponent(datasetVersionId);
  return request<RowOverrideSummary[]>(
    `/api/v1/companies/${company}/datasets/${dataset}/overrides`,
    { token },
  );
}

export function approveOverride(
  token: string,
  companyId: string,
  overrideId: string,
): Promise<{ override_id: string; dataset_version_id: string; approved_by: string }> {
  const company = encodeURIComponent(companyId);
  const override = encodeURIComponent(overrideId);
  return request(
    `/api/v1/companies/${company}/overrides/${override}/approve`,
    { method: 'POST', token },
  );
}

export function rejectDataset(
  token: string,
  companyId: string,
  datasetVersionId: string,
  reason: string,
): Promise<DatasetDetail> {
  const company = encodeURIComponent(companyId);
  const dataset = encodeURIComponent(datasetVersionId);
  return request<DatasetDetail>(
    `/api/v1/companies/${company}/datasets/${dataset}/reject`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ reason }),
      token,
    },
  );
}

export function fetchMovements(
  token: string,
  companyId: string,
  datasetVersionId: string,
  offset = 0,
  limit = 50,
): Promise<Movement[]> {
  const company = encodeURIComponent(companyId);
  const dataset = encodeURIComponent(datasetVersionId);
  return request<Movement[]>(
    `/api/v1/companies/${company}/datasets/${dataset}/movements` +
      `?offset=${Math.max(0, offset)}&limit=${Math.max(1, limit)}`,
    { token },
  );
}

export function fetchMovement(
  token: string,
  companyId: string,
  movementId: string,
): Promise<MovementDetail> {
  const company = encodeURIComponent(companyId);
  const movement = encodeURIComponent(movementId);
  return request<MovementDetail>(
    `/api/v1/companies/${company}/movements/${movement}`,
    { token },
  );
}

export function fetchReconciliationCandidates(
  token: string,
  companyId: string,
  leftDatasetId: string,
  rightDatasetId: string,
  maxDays: number,
  offset: number,
  limit: number,
): Promise<CandidatePage> {
  const company = encodeURIComponent(companyId);
  const query = new URLSearchParams({
    left_dataset_id: leftDatasetId,
    right_dataset_id: rightDatasetId,
    max_days: String(maxDays),
    offset: String(offset),
    limit: String(limit),
  });
  return request<CandidatePage>(
    `/api/v1/companies/${company}/reconciliation/candidates?${query.toString()}`,
    { token },
  );
}

export function fetchReconciliationReviews(
  token: string,
  companyId: string,
  leftDatasetId: string,
  rightDatasetId: string,
): Promise<MatchReview[]> {
  const company = encodeURIComponent(companyId);
  const query = new URLSearchParams({
    left_dataset_id: leftDatasetId,
    right_dataset_id: rightDatasetId,
  });
  return request<MatchReview[]>(
    `/api/v1/companies/${company}/reconciliation/reviews?${query.toString()}`,
    { token },
  );
}

export function fetchReconciliationReview(
  token: string,
  companyId: string,
  candidateId: string,
): Promise<MatchReview> {
  const company = encodeURIComponent(companyId);
  const candidate = encodeURIComponent(candidateId);
  return request<MatchReview>(
    `/api/v1/companies/${company}/reconciliation/reviews/${candidate}`,
    { token },
  );
}

export function fetchReviewQueue(
  token: string,
  companyId: string,
  status: ReviewQueueStatus = 'open',
  offset = 0,
  limit = 50,
): Promise<ReviewQueuePage> {
  const company = encodeURIComponent(companyId);
  const query = new URLSearchParams({
    status,
    offset: String(Math.max(0, offset)),
    limit: String(Math.max(1, Math.min(100, limit))),
  });
  return request<ReviewQueuePage>(
    `/api/v1/companies/${company}/reconciliation/review-queue?${query.toString()}`,
    { token },
  );
}

export function proposeReconciliationReview(
  token: string,
  companyId: string,
  idempotencyKey: string,
  body: {
    left_dataset_id: string;
    right_dataset_id: string;
    left_movement_id: string;
    right_movement_id: string;
    max_days: number;
  },
): Promise<MatchReview> {
  const company = encodeURIComponent(companyId);
  return request<MatchReview>(
    `/api/v1/companies/${company}/reconciliation/reviews`,
    {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'idempotency-key': idempotencyKey,
      },
      body: JSON.stringify(body),
      token,
    },
  );
}

export function decideReconciliationReview(
  token: string,
  companyId: string,
  candidateId: string,
  idempotencyKey: string,
  decision: 'confirmed' | 'rejected',
  reasonCode: string,
): Promise<MatchReview> {
  const company = encodeURIComponent(companyId);
  const candidate = encodeURIComponent(candidateId);
  return request<MatchReview>(
    `/api/v1/companies/${company}/reconciliation/reviews/${candidate}/decision`,
    {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'idempotency-key': idempotencyKey,
      },
      body: JSON.stringify({ decision, reason_code: reasonCode }),
      token,
    },
  );
}

export function fetchReconciliationGroups(
  token: string,
  companyId: string,
  leftDatasetId: string,
  rightDatasetId: string,
): Promise<MatchGroupProposal[]> {
  const company = encodeURIComponent(companyId);
  const query = new URLSearchParams({
    left_dataset_id: leftDatasetId,
    right_dataset_id: rightDatasetId,
    limit: '100',
  });
  return request<MatchGroupProposal[]>(
    `/api/v1/companies/${company}/reconciliation/group-proposals?${query.toString()}`,
    { token },
  );
}

export function proposeReconciliationGroup(
  token: string,
  companyId: string,
  idempotencyKey: string,
  body: {
    anchor_dataset_id: string;
    related_dataset_id: string;
    anchor_movement_id: string;
    related_movement_ids: string[];
  },
): Promise<MatchGroupProposal> {
  const company = encodeURIComponent(companyId);
  return request<MatchGroupProposal>(
    `/api/v1/companies/${company}/reconciliation/group-proposals`,
    {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'idempotency-key': idempotencyKey,
      },
      body: JSON.stringify(body),
      token,
    },
  );
}

export type CorrectionTarget = {
  field: string;
  value_type: string;
  current_value: string | null;
  expected_base_digest: string;
};

export type CorrectionProposal = {
  overlay_id: string;
  dataset_version_id: string;
  movement_id: string;
  field: string;
  value_type: string;
  proposed_value: string;
  reason_code: string;
  reason_comment: string;
  sequence: number;
  created_by: string;
  author_name: string;
  created_at: string;
  status: 'pending_review' | 'approved' | 'rejected' | 'applied';
  applied: boolean;
  reviewer_id: string | null;
  reviewer_name: string | null;
  review_rationale: string | null;
  reviewed_at: string | null;
  result_dataset_version_id: string | null;
};

export type CorrectionApplicationResult = {
  application_id: string;
  base_dataset_version_id: string;
  result_dataset_version_id: string;
  overlay_set_digest: string;
  applied_at: string;
  state: 'validated';
  movement_count: number;
  applied_correction_count: number;
  idempotent_replay: boolean;
};

export function fetchCorrectionTargets(
  token: string,
  companyId: string,
  datasetVersionId: string,
  movementId: string,
): Promise<CorrectionTarget[]> {
  const company = encodeURIComponent(companyId);
  const dataset = encodeURIComponent(datasetVersionId);
  const movement = encodeURIComponent(movementId);
  return request<CorrectionTarget[]>(
    `/api/v1/companies/${company}/datasets/${dataset}/movements/${movement}` +
      '/correction-targets',
    { token },
  );
}

export function fetchCorrections(
  token: string,
  companyId: string,
  datasetVersionId: string,
): Promise<CorrectionProposal[]> {
  const company = encodeURIComponent(companyId);
  const dataset = encodeURIComponent(datasetVersionId);
  return request<CorrectionProposal[]>(
    `/api/v1/companies/${company}/datasets/${dataset}/corrections`,
    { token },
  );
}

export function proposeCorrection(
  token: string,
  companyId: string,
  datasetVersionId: string,
  body: {
    movement_id: string;
    field: string;
    expected_base_digest: string;
    new_value: string;
    reason_code: string;
    reason_comment: string;
  },
): Promise<CorrectionProposal> {
  const company = encodeURIComponent(companyId);
  const dataset = encodeURIComponent(datasetVersionId);
  return request<CorrectionProposal>(
    `/api/v1/companies/${company}/datasets/${dataset}/corrections`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
      token,
    },
  );
}

export function reviewCorrection(
  token: string,
  companyId: string,
  overlayId: string,
  decision: 'approved' | 'rejected',
  rationale: string,
): Promise<{ decision: string; applied: false }> {
  const company = encodeURIComponent(companyId);
  const overlay = encodeURIComponent(overlayId);
  return request(`/api/v1/companies/${company}/corrections/${overlay}/review`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ decision, rationale }),
    token,
  });
}

export function applyApprovedCorrections(
  token: string,
  companyId: string,
  datasetVersionId: string,
): Promise<CorrectionApplicationResult> {
  const company = encodeURIComponent(companyId);
  const dataset = encodeURIComponent(datasetVersionId);
  return request<CorrectionApplicationResult>(
    `/api/v1/companies/${company}/datasets/${dataset}/corrections/apply`,
    { method: 'POST', token },
  );
}





// --------------------------------------------------------------------------- //
// Alta de cuentas, fuentes, vinculos y ciclos (FNC-P3.5)
// --------------------------------------------------------------------------- //

/** Una cuenta. **Nunca** lleva el identificador: solo su cola visible. */
export type Account = {
  account_id: string;
  account_family: string;
  display_name: string;
  identifier_last4: string | null;
  currency_code: string;
  timezone: string;
  status: string;
  closed_reason: string | null;
  created_at: string;
  updated_at?: string;
  usage?: { movements: number; links: number };
};

export type Source = {
  data_source_id: string;
  source_family: string;
  display_name: string;
  purpose_code: string;
  timezone: string;
  status: string;
  closed_reason: string | null;
  created_at: string;
  updated_at?: string;
};

export type SourceLink = {
  link_id: string;
  data_source_id: string;
  financial_account_id: string;
  relation_role: string;
  valid_from: string;
  valid_to: string | null;
  status: string;
  source_name?: string;
  account_name?: string;
  currency_code?: string;
  identifier_last4?: string | null;
  account_status?: string;
};

export type SourceCycle = {
  cycle_id: string;
  responsible_eligible?: boolean;
  data_source_id: string;
  periodicity: string;
  custom_days: number | null;
  due_day_offset: number;
  grace_days: number;
  responsible_subject_id: string;
  timezone: string;
  anchor_date: string;
  status: string;
};

export type Expectation = {
  expectation_id: string;
  data_source_id: string;
  period_start: string;
  period_end: string;
  due_on: string;
  late_after: string;
  state: string;
  stored_state: string;
  days_late: number;
  source_name: string;
  waived_reason: string | null;
};

export type OperationalReminderState =
  | 'overdue'
  | 'in_grace'
  | 'due_today'
  | 'due_soon'
  | 'upcoming'
  | 'satisfied'
  | 'waived';

export type OperationalPeriod = {
  expectation_id: string;
  data_source_id: string;
  source_name: string;
  period_start: string;
  period_end: string;
  due_on: string;
  late_after: string;
  stored_state: string;
  satisfied_at: string | null;
  waived_reason: string | null;
  responsible_subject_id: string | null;
  responsible_name: string | null;
  responsible_eligible: boolean;
  assigned_to_me: boolean;
  timezone: string;
  local_as_of: string;
  reminder_state: OperationalReminderState;
  days_late: number;
  days_until_due: number | null;
};

export type OperationalSummary = {
  period_count: number;
  source_count: number;
  overdue: number;
  in_grace: number;
  due_today: number;
  due_soon: number;
  upcoming: number;
  satisfied: number;
  waived: number;
  filtered_total: number;
  oldest_due_on: string | null;
  newest_due_on: string | null;
};

export type OperationalFilter =
  | 'attention'
  | OperationalReminderState
  | 'all';

export type OperationalPeriodPage = {
  evaluated_at: string;
  local_as_of_dates: string[];
  filter: OperationalFilter;
  limit: number;
  has_more: boolean;
  next_cursor: string | null;
  summary: OperationalSummary;
  items: OperationalPeriod[];
  notice: string;
};

export type SourceDetail = Source & {
  links: SourceLink[];
  cycle: SourceCycle | null;
};

export function fetchAccountsFull(token: string, companyId: string): Promise<Account[]> {
  return request<Account[]>(
    `/api/v1/companies/${encodeURIComponent(companyId)}/accounts`, { token });
}

export function fetchAccount(
  token: string,
  companyId: string,
  accountId: string,
): Promise<Account> {
  const company = encodeURIComponent(companyId);
  return request<Account>(
    `/api/v1/companies/${company}/accounts/${encodeURIComponent(accountId)}`,
    { token },
  );
}

export function createAccount(
  token: string,
  companyId: string,
  body: {
    account_family: string;
    display_name: string;
    identifier: string;
    currency_code: string;
    timezone: string;
  },
): Promise<Account> {
  return request<Account>(
    `/api/v1/companies/${encodeURIComponent(companyId)}/accounts`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
      token,
    },
  );
}

export function updateAccount(
  token: string,
  companyId: string,
  accountId: string,
  body: { status?: string; closed_reason?: string; display_name?: string },
): Promise<Account> {
  const company = encodeURIComponent(companyId);
  return request<Account>(
    `/api/v1/companies/${company}/accounts/${encodeURIComponent(accountId)}`,
    {
      method: 'PATCH',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
      token,
    },
  );
}

export function fetchSourcesFull(token: string, companyId: string): Promise<Source[]> {
  return request<Source[]>(
    `/api/v1/companies/${encodeURIComponent(companyId)}/sources`, { token });
}

export function fetchSource(
  token: string,
  companyId: string,
  sourceId: string,
): Promise<SourceDetail> {
  const company = encodeURIComponent(companyId);
  return request<SourceDetail>(
    `/api/v1/companies/${company}/sources/${encodeURIComponent(sourceId)}`,
    { token },
  );
}

export function createSource(
  token: string,
  companyId: string,
  body: {
    source_family: string;
    display_name: string;
    purpose_code: string;
    timezone: string;
  },
): Promise<Source> {
  return request<Source>(
    `/api/v1/companies/${encodeURIComponent(companyId)}/sources`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
      token,
    },
  );
}

export function linkAccount(
  token: string,
  companyId: string,
  sourceId: string,
  body: { financial_account_id: string; relation_role: string },
): Promise<SourceLink> {
  const company = encodeURIComponent(companyId);
  return request<SourceLink>(
    `/api/v1/companies/${company}/sources/${encodeURIComponent(sourceId)}/accounts`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
      token,
    },
  );
}

export function fetchLinks(token: string, companyId: string): Promise<SourceLink[]> {
  return request<SourceLink[]>(
    `/api/v1/companies/${encodeURIComponent(companyId)}/links`, { token });
}

export function setCycle(
  token: string,
  companyId: string,
  sourceId: string,
  body: {
    periodicity: string;
    custom_days: number | null;
    due_day_offset: number;
    grace_days: number;
    responsible_subject_id: string;
    timezone: string;
    anchor_date: string;
  },
): Promise<SourceCycle> {
  const company = encodeURIComponent(companyId);
  return request<SourceCycle>(
    `/api/v1/companies/${company}/sources/${encodeURIComponent(sourceId)}/cycle`,
    {
      method: 'PUT',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
      token,
    },
  );
}

export function generateExpectations(
  token: string,
  companyId: string,
  sourceId: string,
  until: string,
): Promise<{ periods: number; created: number }> {
  const company = encodeURIComponent(companyId);
  return request(
    `/api/v1/companies/${company}/sources/${encodeURIComponent(sourceId)}/expectations`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ until }),
      token,
    },
  );
}

export function fetchExpectations(
  token: string,
  companyId: string,
): Promise<Expectation[]> {
  return request<Expectation[]>(
    `/api/v1/companies/${encodeURIComponent(companyId)}/expectations?limit=100`,
    { token },
  );
}

export function fetchOperationalPeriods(
  token: string,
  companyId: string,
  status: OperationalFilter,
  limit = 50,
  cursor?: string,
): Promise<OperationalPeriodPage> {
  const query = new URLSearchParams({
    status,
    limit: String(Math.max(1, Math.min(50, limit))),
  });
  if (cursor) query.set('cursor', cursor);
  return request<OperationalPeriodPage>(
    `/api/v1/companies/${encodeURIComponent(companyId)}/operations/periods?${query}`,
    { token },
  );
}

export type CloseReadinessControl = {
  code: string;
  state: 'pass' | 'blocked' | 'unavailable';
  count: number;
  detail: string;
};

export type CloseReadinessSource = {
  expectation_id: string;
  data_source_id: string;
  source_name: string;
  financial_account_id: string | null;
  period_start: string;
  period_end: string;
  expectation_state: string;
  satisfied_by_artifact_id: string | null;
  dataset_version_id: string | null;
  dataset_state: string | null;
  completeness_state: string | null;
  lineage_state: string | null;
  rejected_count: number;
  movement_count: number;
  prepared_at: string | null;
  account_name: string | null;
  selection_rule: string;
};

export type CloseReadinessBlocker = {
  code: string;
  count: number;
  detail: string;
};

export type CloseReadinessAccountReconciliation = {
  financial_account_id: string;
  account_name: string | null;
  source_count: number;
  assessment_count: number;
  statement_root_id: string | null;
  statement_id: string | null;
  statement_version: number | null;
  statement_state: string | null;
  statement_lineage_state: string | null;
  coverage_state:
    | 'covered'
    | 'missing_assessment'
    | 'missing_statement'
    | 'stale_inputs'
    | 'review_required';
};

export type CloseReadinessPeriod = {
  period_start: string;
  period_end: string;
  status: 'blocked' | 'ready_for_review';
  close_ready: false;
  can_execute_close: false;
  source_count: number;
  selected_dataset_count: number;
  expected_account_count: number;
  missing_account_assignment_count: number;
  controls: CloseReadinessControl[];
  blockers: CloseReadinessBlocker[];
  sources: CloseReadinessSource[];
  account_reconciliations: CloseReadinessAccountReconciliation[];
};

export type CloseReadinessResult = {
  mode: 'diagnostic_only';
  close_ready: false;
  can_execute_close: false;
  period_count: number;
  blocked_period_count: number;
  review_ready_period_count: number;
  source_count: number;
  limit: number;
  items: CloseReadinessPeriod[];
  notice: string;
};

export type StatementLineageInput = {
  node_type: 'financial_fact_field' | 'decision';
  entity_ref: string;
  field_name: string;
  value_digest: string;
  operation: 'decided_using';
  processing_run_id: string;
  engine_release_id: string;
  canonical_schema_version: string;
};

export type StatementLineage = {
  statement_id: string;
  lineage_state: 'required_pending' | 'complete' | 'invalidated';
  complete: boolean;
  inputs: StatementLineageInput[];
  notice: 'digest_only_lineage; no values or close authority';
};

export function fetchCloseReadiness(
  token: string,
  companyId: string,
  limit = 12,
): Promise<CloseReadinessResult> {
  const bounded = Math.max(1, Math.min(24, limit));
  return request<CloseReadinessResult>(
    `/api/v1/companies/${encodeURIComponent(companyId)}/close-readiness?limit=${bounded}`,
    { token },
  );
}

export function fetchStatementLineage(
  token: string,
  companyId: string,
  statementId: string,
): Promise<StatementLineage> {
  const company = encodeURIComponent(companyId);
  const statement = encodeURIComponent(statementId);
  return request<StatementLineage>(
    `/api/v1/companies/${company}/balance-reconciliation/statements/${statement}/lineage`,
    { token },
  );
}

export type CloseReviewManifest = {
  schema_version: 'close-evidence-v1';
  diagnostic_status: 'blocked' | 'ready_for_review';
  controls: Array<{ code: string; state: string; count: number }>;
  sources: Array<{
    expectation_id: string;
    data_source_id: string;
    financial_account_id: string | null;
    expectation_state: string;
    dataset_version_id: string | null;
    dataset_state: string | null;
    completeness_state: string | null;
    lineage_state: string | null;
    rejected_count: number;
    movement_count: number;
  }>;
  accounts: Array<{
    financial_account_id: string;
    source_count: number;
    assessment_count: number;
    statement_root_id: string | null;
    statement_id: string | null;
    statement_version: number | null;
    statement_state: string | null;
    statement_lineage_state: string | null;
    coverage_state: string;
  }>;
};

export type CloseReviewReviewer = {
  subject_id: string;
  display_name: string;
  company_roles: string[];
};

export type CloseReviewPacket = {
  packet_id: string;
  period_start: string;
  period_end: string;
  version: number;
  manifest_schema_version: 'close-evidence-v1';
  manifest: CloseReviewManifest;
  manifest_digest: string;
  diagnostic_status: 'blocked' | 'ready_for_review';
  prepared_by: string;
  preparer_name: string;
  assigned_reviewer_id: string;
  reviewer_name: string;
  prepared_at: string;
  decision_id: string | null;
  decision: 'evidence_reviewed' | 'changes_requested' | null;
  reason_code: string | null;
  decided_by: string | null;
  decider_name: string | null;
  decided_at: string | null;
  reviewer_eligible: boolean;
  status: 'pending_review' | 'evidence_reviewed' | 'changes_requested';
  replayed: boolean;
  financial_effect: 'none';
  certifies_close: false;
  can_execute_close: false;
};

export type CloseReviewPage = {
  items: CloseReviewPacket[];
  has_more: boolean;
  limit: number;
  financial_effect: 'none';
  certifies_close: false;
  can_execute_close: false;
};

export function fetchCloseReviewers(
  token: string,
  companyId: string,
): Promise<CloseReviewReviewer[]> {
  return request<CloseReviewReviewer[]>(
    `/api/v1/companies/${encodeURIComponent(companyId)}/close-review/reviewers`,
    { token },
  );
}

export function fetchCloseReviewPackets(
  token: string,
  companyId: string,
  limit = 100,
): Promise<CloseReviewPage> {
  const bounded = Math.max(1, Math.min(100, limit));
  return request<CloseReviewPage>(
    `/api/v1/companies/${encodeURIComponent(companyId)}/close-review/packets?limit=${bounded}`,
    { token },
  );
}

export function prepareCloseReviewPacket(
  token: string,
  companyId: string,
  idempotencyKey: string,
  input: {
    period_start: string;
    period_end: string;
    assigned_reviewer_id: string;
  },
): Promise<CloseReviewPacket> {
  return request<CloseReviewPacket>(
    `/api/v1/companies/${encodeURIComponent(companyId)}/close-review/packets`,
    {
      method: 'POST', token,
      headers: {
        'content-type': 'application/json',
        'idempotency-key': idempotencyKey,
      },
      body: JSON.stringify(input),
    },
  );
}

export function decideCloseReviewPacket(
  token: string,
  companyId: string,
  packetId: string,
  idempotencyKey: string,
  input: {
    decision: 'evidence_reviewed' | 'changes_requested';
    reason_code: string;
  },
): Promise<CloseReviewPacket> {
  const company = encodeURIComponent(companyId);
  const packet = encodeURIComponent(packetId);
  return request<CloseReviewPacket>(
    `/api/v1/companies/${company}/close-review/packets/${packet}/decision`,
    {
      method: 'POST', token,
      headers: {
        'content-type': 'application/json',
        'idempotency-key': idempotencyKey,
      },
      body: JSON.stringify(input),
    },
  );
}

export type AccountBalance = {
  balance_id: string;
  financial_account_id: string;
  account_name: string;
  source_record_id: string;
  source_name: string;
  record_ordinal: number;
  balance_type: 'opening' | 'closing' | 'running' | 'available' | 'ledger';
  amount: string;
  currency_code: string;
  as_of: string;
  source_timezone: string;
  amount_field_index: number;
  as_of_field_index: number;
  lineage_state: 'required_pending' | 'complete' | 'invalidated';
  created_at: string;
  replayed: boolean;
  proves_completeness: false;
  proves_reconciliation: false;
};

export type AccountBalancePage = {
  limit: number;
  truncated: boolean;
  items: AccountBalance[];
  notice: string;
};

export type BalanceEvidenceField = {
  index: number;
  label: string;
  value: string;
};

export type BalanceEvidence = {
  source_record_id: string;
  dataset_version_id: string;
  source_name: string;
  financial_account_id: string;
  account_name: string;
  currency_code: string;
  record_ordinal: number;
  source_timezone: string;
  fields: BalanceEvidenceField[];
};

export type BalanceEvidencePage = {
  limit: number;
  truncated: boolean;
  items: BalanceEvidence[];
};

export function fetchAccountBalances(
  token: string,
  companyId: string,
  limit = 100,
): Promise<AccountBalancePage> {
  return request<AccountBalancePage>(
    `/api/v1/companies/${encodeURIComponent(companyId)}/balances` +
      `?limit=${Math.max(1, Math.min(200, limit))}`,
    { token },
  );
}

export function fetchBalanceEvidence(
  token: string,
  companyId: string,
  limit = 20,
): Promise<BalanceEvidencePage> {
  return request<BalanceEvidencePage>(
    `/api/v1/companies/${encodeURIComponent(companyId)}/balances/evidence` +
      `?limit=${Math.max(1, Math.min(50, limit))}`,
    { token },
  );
}

export function createAccountBalance(
  token: string,
  companyId: string,
  body: {
    source_record_id: string;
    balance_type: AccountBalance['balance_type'];
    amount_field_index: number;
    as_of_field_index: number;
  },
): Promise<AccountBalance> {
  return request<AccountBalance>(
    `/api/v1/companies/${encodeURIComponent(companyId)}/balances`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
      token,
    },
  );
}

export type ReconciliationExpectation = {
  expectation_id: string;
  data_source_id: string;
  source_name: string;
  financial_account_id: string | null;
  account_name: string | null;
  period_start: string;
  period_end: string;
  state: string;
  has_artifact: boolean;
  assessed: boolean;
};

export type CompletenessControlResult = {
  control_result_id: string;
  assessment_id: string;
  control_type: string;
  required: boolean;
  outcome: 'match' | 'mismatch' | 'unknown' | 'not_applicable';
  expected_value: unknown;
  observed_value: unknown;
  value_type: string;
  reason: string | null;
  lineage_state: 'required_pending' | 'complete' | 'invalidated';
};

export type CompletenessAssessment = {
  assessment_id: string;
  data_source_id: string;
  source_name: string;
  source_expectation_id: string;
  financial_account_id: string | null;
  account_name: string | null;
  dataset_version_id: string;
  period_start: string;
  period_end: string;
  state: 'verified' | 'mismatch' | 'unknown' | 'accepted_exception';
  lineage_state: 'required_pending' | 'complete' | 'invalidated';
  created_at: string;
  replayed: boolean;
  controls: CompletenessControlResult[];
};

export type ReconcilingItem = {
  item_decision_id: string;
  item_root_id: string;
  statement_root_id: string;
  adjustment_side: 'add_to_bank' | 'deduct_from_bank';
  amount: string;
  currency_code: string;
  reason_code: string;
  state: 'proposed' | 'confirmed' | 'rejected' | 'reversed';
  prepared_by: string;
  approved_by: string | null;
  decision_version: number;
  lineage_state: 'required_pending' | 'complete' | 'invalidated';
  created_at: string;
  replayed?: boolean;
};

export type BalanceReconciliationStatement = {
  statement_id: string;
  statement_root_id: string;
  version: number;
  financial_account_id: string;
  account_name: string;
  period_start: string;
  period_end: string;
  currency_code: string;
  bank_closing_balance_id: string;
  books_closing_balance_id: string;
  completeness_assessment_ids: string[];
  confirmed_reconciling_item_ids: string[];
  bank_closing_balance: string;
  books_closing_balance: string;
  confirmed_additions_to_bank: string;
  confirmed_deductions_from_bank: string;
  adjusted_bank_balance: string;
  unexplained_difference: string;
  state: 'draft' | 'review_required' | 'balanced' | 'exception_accepted' | 'superseded';
  lineage_state: 'required_pending' | 'complete' | 'invalidated';
  created_at: string;
  replayed: boolean;
  certifies_close: false;
};

export type BalanceReconciliationWorkspace = {
  limit: number;
  truncated: boolean;
  totals: { expectations: number; assessments: number; statements: number; items: number };
  expectations: ReconciliationExpectation[];
  assessments: CompletenessAssessment[];
  statements: BalanceReconciliationStatement[];
  items: ReconcilingItem[];
  notice: string;
};

const reconciliationPath = (companyId: string): string =>
  `/api/v1/companies/${encodeURIComponent(companyId)}/balance-reconciliation`;

export function fetchBalanceReconciliation(
  token: string,
  companyId: string,
  limit = 50,
): Promise<BalanceReconciliationWorkspace> {
  return request<BalanceReconciliationWorkspace>(
    `${reconciliationPath(companyId)}?limit=${Math.max(1, Math.min(100, limit))}`,
    { token },
  );
}

export function createCompletenessAssessment(
  token: string,
  companyId: string,
  expectationId: string,
): Promise<CompletenessAssessment> {
  return request<CompletenessAssessment>(
    `${reconciliationPath(companyId)}/assessments`,
    {
      method: 'POST', token,
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ expectation_id: expectationId }),
    },
  );
}

export function createBalanceReconciliationStatement(
  token: string,
  companyId: string,
  body: {
    bank_balance_id: string;
    books_balance_id: string;
    assessment_ids: string[];
  },
): Promise<BalanceReconciliationStatement> {
  return request<BalanceReconciliationStatement>(
    `${reconciliationPath(companyId)}/statements`,
    {
      method: 'POST', token,
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    },
  );
}

export function createReconcilingItem(
  token: string,
  companyId: string,
  statementRootId: string,
  body: {
    amount: string;
    adjustment_side: ReconcilingItem['adjustment_side'];
    reason_code: string;
    evidence_source_record_ids: string[];
  },
): Promise<ReconcilingItem> {
  return request<ReconcilingItem>(
    `${reconciliationPath(companyId)}/statements/` +
      `${encodeURIComponent(statementRootId)}/items`,
    {
      method: 'POST', token,
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    },
  );
}

export function decideReconcilingItem(
  token: string,
  companyId: string,
  itemRootId: string,
  decision: 'confirmed' | 'rejected' | 'reversed',
): Promise<ReconcilingItem> {
  return request<ReconcilingItem>(
    `${reconciliationPath(companyId)}/items/${encodeURIComponent(itemRootId)}/decisions`,
    {
      method: 'POST', token,
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ decision }),
    },
  );
}

export function continueDataset(
  token: string,
  companyId: string,
  datasetVersionId: string,
): Promise<{ state: string; complete: boolean; movement_count: number }> {
  const company = encodeURIComponent(companyId);
  const dataset = encodeURIComponent(datasetVersionId);
  return request(`/api/v1/companies/${company}/datasets/${dataset}/continue`, {
    method: 'POST',
    token,
  });
}

/** Alguien que puede responder de un ciclo. Sin correo y sin vinculo externo. */
export type Assignee = {
  subject_id: string;
  display_name: string;
  company_roles: string[];
};

export function fetchAssignees(
  token: string,
  companyId: string,
): Promise<Assignee[]> {
  return request<Assignee[]>(
    `/api/v1/companies/${encodeURIComponent(companyId)}/assignees`,
    { token },
  );
}

// --------------------------------------------------------------------------- //
// Equipo y roles company-scoped (FNC-QA-007)
// --------------------------------------------------------------------------- //

/** Miembro activo de la firma delegada. No contiene correo ni identidad externa. */
export type CompanyMember = {
  subject_id: string;
  display_name: string;
  firm_role: string;
  company_roles: string[];
};

export type RoleChangeResult = {
  subject_id: string;
  role: string;
  changed: boolean;
  replayed: boolean;
  authorization_version: number;
  refreshed_session: null | {
    token: string;
    expires_at: number;
    display_name: string;
  };
};

export function fetchMembers(
  token: string,
  companyId: string,
): Promise<CompanyMember[]> {
  return request<CompanyMember[]>(
    `/api/v1/companies/${encodeURIComponent(companyId)}/members`,
    { token },
  );
}

function changeMemberRole(
  method: 'POST' | 'DELETE',
  token: string,
  companyId: string,
  subjectId: string,
  body: { role: string; reason_code: string },
): Promise<RoleChangeResult> {
  const company = encodeURIComponent(companyId);
  const subject = encodeURIComponent(subjectId);
  return request<RoleChangeResult>(
    `/api/v1/companies/${company}/members/${subject}/roles`,
    {
      method,
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
      token,
    },
  );
}

export function grantMemberRole(
  token: string,
  companyId: string,
  subjectId: string,
  body: { role: string; reason_code: string },
): Promise<RoleChangeResult> {
  return changeMemberRole('POST', token, companyId, subjectId, body);
}

export function revokeMemberRole(
  token: string,
  companyId: string,
  subjectId: string,
  body: { role: string; reason_code: string },
): Promise<RoleChangeResult> {
  return changeMemberRole('DELETE', token, companyId, subjectId, body);
}

// --------------------------------------------------------------------------- //
// Centro de calidad y anomalias deterministas (FNC-DQ-001)
// --------------------------------------------------------------------------- //

export type QualityStatus = 'open' | 'acknowledged' | 'resolved' | 'dismissed';
export type QualitySeverity = 'info' | 'warning' | 'high';
export type QualityRule =
  | 'dataset_completeness_mismatch'
  | 'dataset_completeness_unknown'
  | 'dataset_rejected_records'
  | 'lineage_invalidated'
  | 'duplicate_fingerprint'
  | 'reference_amount_conflict'
  | 'posting_delay_over_31_days'
  | 'amount_outlier_10x_median';

export type QualityIssue = {
  issue_id: string;
  rule_code: QualityRule;
  rule_version: string;
  scope_kind: 'dataset' | 'movement';
  scope_ref: string;
  severity: QualitySeverity;
  status: QualityStatus;
  occurrence_count: number;
  assigned_to: string | null;
  assigned_to_name: string | null;
  reviewed_by: string | null;
  reviewed_by_name: string | null;
  resolution_reason: string | null;
  first_seen_at: string;
  last_seen_at: string;
  updated_at: string;
  financial_effect: 'none';
  proves_fraud: false;
};

export type QualityIssuePage = {
  filter: { status: QualityStatus | 'all'; severity: QualitySeverity | 'all'; rule: QualityRule | 'all' };
  offset: number;
  limit: number;
  truncated: boolean;
  summary: {
    total: number;
    open: number;
    acknowledged: number;
    resolved: number;
    dismissed: number;
    high: number;
    warning: number;
    info: number;
  };
  items: QualityIssue[];
  notice: string;
};

export type QualityScanResult = {
  rule_version: string;
  datasets_examined_limit: number;
  findings: number;
  created: number;
  refreshed: number;
  truncated: boolean;
  truncated_rules: QualityRule[];
  financial_effect: 'none';
};

export function fetchQualityIssues(
  token: string,
  companyId: string,
  filters: { status?: string; severity?: string; rule?: string; limit?: number } = {},
): Promise<QualityIssuePage> {
  const query = new URLSearchParams({
    status: filters.status ?? 'open',
    severity: filters.severity ?? 'all',
    rule: filters.rule ?? 'all',
    limit: String(Math.max(1, Math.min(100, filters.limit ?? 50))),
  });
  return request<QualityIssuePage>(
    `/api/v1/companies/${encodeURIComponent(companyId)}/quality/issues?${query}`,
    { token },
  );
}

export function scanQualityIssues(
  token: string,
  companyId: string,
): Promise<QualityScanResult> {
  return request<QualityScanResult>(
    `/api/v1/companies/${encodeURIComponent(companyId)}/quality/scan`,
    { method: 'POST', token },
  );
}

export function triageQualityIssue(
  token: string,
  companyId: string,
  issueId: string,
  body: { status: string; reason_code: string; rationale: string },
): Promise<QualityIssue & { replayed: boolean }> {
  const company = encodeURIComponent(companyId);
  const issue = encodeURIComponent(issueId);
  return request(`/api/v1/companies/${company}/quality/issues/${issue}`, {
    method: 'PATCH',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
    token,
  });
}

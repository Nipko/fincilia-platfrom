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

/** Fallo con el codigo que devolvio la API, para poder distinguir 401 de 403. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
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
      try {
        const problem = (await response.json()) as { detail?: unknown };
        if (typeof problem.detail === 'string') {
          detail = problem.detail;
        }
      } catch {
        /* un cuerpo ilegible no cambia el codigo de estado */
      }
      throw new ApiError(response.status, detail);
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

export type ArtifactDetail = ArtifactSummary & { runs: ProcessingRun[] };

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
  encoding: string;
  delimiter: string;
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
  ignored_columns: number[];
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

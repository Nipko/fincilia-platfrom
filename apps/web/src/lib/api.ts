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

function baseUrl(): string {
  const configured = process.env.FINCILIA_API_BASE_URL;
  if (!configured) {
    // Sin base de API no hay nada que ensenar. Fallar aqui es mejor que
    // adivinar un `localhost` que en un contenedor no existe.
    throw new Error('FINCILIA_API_BASE_URL is required');
  }
  return configured.replace(/\/+$/, '');
}

async function request<T>(
  path: string,
  init: RequestInit & { token?: string } = {},
): Promise<T> {
  const { token, headers, ...rest } = init;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(`${baseUrl()}${path}`, {
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
  } catch {
    throw new ApiError(503, 'no se pudo contactar con la API');
  } finally {
    clearTimeout(timer);
  }

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
  return (await response.json()) as T;
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

export function uploadDocument(
  token: string,
  companyId: string,
  file: File,
): Promise<ArtifactSummary> {
  const body = new FormData();
  body.append('file', file, file.name);
  // Sin `content-type` a mano: lo pone `fetch` con el `boundary` que corresponde,
  // y escribirlo aqui produce un cuerpo que el servidor no sabe partir.
  return request<ArtifactSummary>(
    `/api/v1/companies/${encodeURIComponent(companyId)}/documents`,
    { method: 'POST', body, token },
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

export type MappingDetail = MappingVersion & {
  decisions: MappingDecision[];
  blockers: Blocker[];
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
  prepared_by: string;
  validated_by: string | null;
  published_by: string | null;
  rejected_reason: string | null;
  canonical_schema_version: string;
  engine_release: string;
  can_publish: boolean;
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

export type LineageStep = {
  field: string;
  cell: OriginLocator;
  transform: string;
  value_digest: string;
  operation: string;
};

export type MovementDetail = Movement & {
  dataset_version_id: string;
  dataset_state: string;
  origin: { filename: string; locator: OriginLocator; values: string[] };
  lineage: LineageStep[];
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
  artifactId: string,
): Promise<DatasetSummary[]> {
  const company = encodeURIComponent(companyId);
  const artifact = encodeURIComponent(artifactId);
  return request<DatasetSummary[]>(
    `/api/v1/companies/${company}/datasets?artifact_id=${artifact}`,
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

export type FinancialAccount = {
  account_id: string;
  account_family: string;
  display_name: string;
  identifier_last4: string | null;
  currency_code: string;
  status: string;
};

export type DataSource = {
  data_source_id: string;
  source_family: string;
  display_name: string;
  timezone: string;
  status: string;
};

export function fetchAccounts(
  token: string,
  companyId: string,
): Promise<FinancialAccount[]> {
  return request<FinancialAccount[]>(
    `/api/v1/companies/${encodeURIComponent(companyId)}/accounts`,
    { token },
  );
}

export function fetchSources(
  token: string,
  companyId: string,
): Promise<DataSource[]> {
  return request<DataSource[]>(
    `/api/v1/companies/${encodeURIComponent(companyId)}/sources`,
    { token },
  );
}

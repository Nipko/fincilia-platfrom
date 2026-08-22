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

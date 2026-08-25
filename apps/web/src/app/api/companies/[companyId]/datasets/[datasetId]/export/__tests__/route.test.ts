import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  apiUrl: vi.fn((path: string) => `http://api.internal${path}`),
  clearSession: vi.fn(async () => undefined),
  readSession: vi.fn(),
}));

vi.mock('@/lib/server-config', () => ({ apiUrl: mocks.apiUrl }));
vi.mock('@/lib/session', () => ({
  clearSession: mocks.clearSession,
  readSession: mocks.readSession,
}));

import { GET } from '../route';

const COMPANY_ID = '5f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5e';
const DATASET_ID = '6f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5f';
const URL =
  `http://fincilia.test/api/companies/${COMPANY_ID}/datasets/` +
  `${DATASET_ID}/export`;

function request(signal?: AbortSignal): Request {
  return new Request(URL, signal ? { signal } : undefined);
}

function context(
  companyId = COMPANY_ID,
  datasetId = DATASET_ID,
) {
  return { params: Promise.resolve({ companyId, datasetId }) };
}

function csvResponse(
  body = '\ufeffrecord_ordinal,amount\r\n2,10.000000000000\r\n',
  overrides: Record<string, string> = {},
): Response {
  return new Response(body, {
    status: 200,
    headers: {
      'content-type': 'text/csv; charset=utf-8',
      'content-disposition':
        'attachment; filename="fincilia-canonico-6f0f7b18-0a7.csv"',
      'cache-control': 'public, max-age=86400',
      'x-fincilia-export-profile': 'canonical-v1',
      'x-fincilia-export-rows': '1',
      'x-fincilia-canonical-schema': 'v1.0',
      'x-internal-detail': 'never-forward',
      ...overrides,
    },
  });
}

describe('GET canonical export BFF', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    vi.clearAllMocks();
    mocks.readSession.mockResolvedValue({ token: 'token-sintetico', displayName: 'Beto' });
  });

  it('limpia cookies y no abre el upstream sin sesion', async () => {
    mocks.readSession.mockResolvedValue(null);
    const upstream = vi.fn();
    vi.stubGlobal('fetch', upstream);

    const response = await GET(request(), context());

    expect(response.status).toBe(401);
    expect(mocks.clearSession).toHaveBeenCalledOnce();
    expect(upstream).not.toHaveBeenCalled();
  });

  it('rechaza ids ambiguos antes del upstream', async () => {
    const upstream = vi.fn();
    vi.stubGlobal('fetch', upstream);

    const response = await GET(request(), context('../empresa', DATASET_ID));

    expect(response.status).toBe(400);
    expect(upstream).not.toHaveBeenCalled();
  });

  it('transmite bytes exactos y solo cabeceras allowlisted', async () => {
    const body = '\ufeffrecord_ordinal,amount\r\n2,10.000000000000\r\n';
    let upstreamInit: RequestInit | undefined;
    const upstream = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      upstreamInit = init;
      return csvResponse(body);
    });
    vi.stubGlobal('fetch', upstream);

    const response = await GET(
      new Request(URL, {
        headers: { cookie: 'never-forward', referer: 'http://fincilia.test/privado' },
      }),
      context(),
    );

    expect(response.status).toBe(200);
    expect(Array.from(new Uint8Array(await response.arrayBuffer()))).toEqual(
      Array.from(new TextEncoder().encode(body)),
    );
    expect(response.headers.get('cache-control')).toBe('private, no-store, max-age=0');
    expect(response.headers.get('x-content-type-options')).toBe('nosniff');
    expect(response.headers.get('x-internal-detail')).toBeNull();
    expect(response.headers.get('content-disposition')).toBe(
      'attachment; filename="fincilia-canonico-6f0f7b18-0a7.csv"',
    );
    expect(upstream).toHaveBeenCalledOnce();
    expect(upstreamInit?.headers).toEqual({
      accept: 'text/csv',
      authorization: 'Bearer token-sintetico',
    });
    expect(String(upstreamInit?.headers)).not.toContain('cookie');
  });

  it('falla cerrado y cancela el cuerpo ante metadatos inesperados', async () => {
    const cancelled = vi.fn();
    const source = new ReadableStream<Uint8Array>({
      pull(controller) {
        controller.enqueue(new TextEncoder().encode('synthetic'));
      },
      cancel: cancelled,
    });
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        const response = csvResponse('', { 'x-fincilia-export-profile': 'latest' });
        return new Response(source, { status: 200, headers: response.headers });
      }),
    );

    const response = await GET(request(), context());

    expect(response.status).toBe(502);
    expect(cancelled).toHaveBeenCalledOnce();
  });

  it.each([
    [401, 401],
    [403, 403],
    [404, 403],
    [409, 409],
    [422, 502],
    [503, 503],
  ])('normaliza el estado upstream %i como %i sin reflejar su cuerpo', async (upstreamStatus, publicStatus) => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response('detalle-interno-sintetico', { status: upstreamStatus }),
      ),
    );

    const response = await GET(request(), context());
    const payload = (await response.json()) as { detail: string };

    expect(response.status).toBe(publicStatus);
    expect(payload.detail).not.toContain('detalle-interno');
    expect(mocks.clearSession).toHaveBeenCalledTimes(upstreamStatus === 401 ? 1 : 0);
  });

  it('no abre el upstream si el cliente ya cancelo', async () => {
    const controller = new AbortController();
    controller.abort();
    const upstream = vi.fn();
    vi.stubGlobal('fetch', upstream);

    const response = await GET(request(controller.signal), context());

    expect(response.status).toBe(499);
    expect(upstream).not.toHaveBeenCalled();
  });
});

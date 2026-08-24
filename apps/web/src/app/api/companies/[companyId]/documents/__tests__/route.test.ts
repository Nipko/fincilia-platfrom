import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  apiUrl: vi.fn((path: string) => `http://api.internal${path}`),
  clearSession: vi.fn(async () => undefined),
  fetchSource: vi.fn(),
  readSession: vi.fn(),
  publicWebOrigin: vi.fn(() => null as string | null),
}));

vi.mock('@/lib/api', () => ({
  ApiError: class ApiError extends Error {
    readonly status: number;

    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
  fetchSource: mocks.fetchSource,
}));
vi.mock('@/lib/server-config', () => ({
  apiUrl: mocks.apiUrl,
  publicWebOrigin: mocks.publicWebOrigin,
}));
vi.mock('@/lib/session', () => ({
  clearSession: mocks.clearSession,
  readSession: mocks.readSession,
}));

import { POST } from '../route';
import { MAX_UPLOAD_ENVELOPE_BYTES } from '@/lib/upload-policy';

const COMPANY_ID = '5f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5e';
const SOURCE_ID = '6f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5f';
const ARTIFACT_ID = '7f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d60';
const URL =
  `http://fincilia.test/api/companies/${COMPANY_ID}/documents?` +
  `sourceId=${SOURCE_ID}`;

function request(
  overrides: Record<string, string> = {},
  body = '--synthetic\r\ncontent\r\n--synthetic--',
  signal?: AbortSignal,
): Request {
  return new Request(URL, {
    method: 'POST',
    headers: {
      origin: 'http://fincilia.test',
      host: 'fincilia.test',
      'content-type': 'multipart/form-data; boundary=synthetic',
      ...overrides,
    },
    body,
    ...(signal ? { signal } : {}),
  });
}

function context() {
  return { params: Promise.resolve({ companyId: COMPANY_ID }) };
}

describe('POST upload BFF', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    vi.clearAllMocks();
    mocks.readSession.mockResolvedValue({ token: 'token-sintetico', displayName: 'Ada' });
    mocks.fetchSource.mockResolvedValue({ status: 'active' });
    mocks.clearSession.mockResolvedValue(undefined);
    mocks.publicWebOrigin.mockReturnValue(null);
  });

  it('rechaza una peticion sin origen antes de consultar sesion o API', async () => {
    const response = await POST(
      new Request(URL, {
        method: 'POST',
        headers: { 'content-type': 'multipart/form-data; boundary=synthetic' },
        body: 'synthetic',
      }),
      context(),
    );

    expect(response.status).toBe(403);
    expect(mocks.readSession).not.toHaveBeenCalled();
    expect(mocks.fetchSource).not.toHaveBeenCalled();
  });

  it('acepta Origin publico aunque request.url use la autoridad interna de Docker', async () => {
    mocks.readSession.mockResolvedValue(null);
    const internalUrl = URL.replace('http://fincilia.test', 'http://0.0.0.0:3000');

    const response = await POST(
      new Request(internalUrl, {
        method: 'POST',
        headers: {
          origin: 'http://127.0.0.1:53000',
          host: '127.0.0.1:53000',
          'content-type': 'multipart/form-data; boundary=synthetic',
        },
        body: 'synthetic',
      }),
      context(),
    );

    expect(response.status).toBe(401);
    expect(mocks.readSession).toHaveBeenCalledOnce();
  });

  it('rechaza Origin y Host divergentes aunque request.url sea interno', async () => {
    const internalUrl = URL.replace('http://fincilia.test', 'http://0.0.0.0:3000');

    const response = await POST(
      new Request(internalUrl, {
        method: 'POST',
        headers: {
          origin: 'http://evil.test',
          host: '127.0.0.1:53000',
          'content-type': 'multipart/form-data; boundary=synthetic',
        },
        body: 'synthetic',
      }),
      context(),
    );

    expect(response.status).toBe(403);
    expect(mocks.readSession).not.toHaveBeenCalled();
  });

  it('limpia cookies y devuelve 401 cuando falta sesion', async () => {
    mocks.readSession.mockResolvedValue(null);

    const response = await POST(request(), context());

    expect(response.status).toBe(401);
    expect(mocks.clearSession).toHaveBeenCalledOnce();
    expect(mocks.fetchSource).not.toHaveBeenCalled();
  });

  it('rechaza longitud declarada sobre el sobre sin contactar upstream', async () => {
    const upstream = vi.fn();
    vi.stubGlobal('fetch', upstream);

    const response = await POST(
      request({ 'content-length': String(MAX_UPLOAD_ENVELOPE_BYTES + 1) }),
      context(),
    );

    expect(response.status).toBe(413);
    expect(mocks.fetchSource).not.toHaveBeenCalled();
    expect(upstream).not.toHaveBeenCalled();
  });

  it('no abre el upstream si el cliente cancela durante la validacion de fuente', async () => {
    let resolveSource: ((value: { status: string }) => void) | undefined;
    mocks.fetchSource.mockReturnValue(
      new Promise((resolve) => {
        resolveSource = resolve;
      }),
    );
    const upstream = vi.fn();
    vi.stubGlobal('fetch', upstream);
    const controller = new AbortController();

    const pending = POST(request({}, 'synthetic', controller.signal), context());
    await vi.waitFor(() => expect(mocks.fetchSource).toHaveBeenCalledOnce());
    controller.abort();
    resolveSource?.({ status: 'active' });

    const response = await pending;
    expect(response.status).toBe(499);
    expect(upstream).not.toHaveBeenCalled();
  });

  it('valida la fuente y reenvia solo headers permitidos', async () => {
    const upstream = vi.fn(async (..._arguments: unknown[]) =>
      new Response(
        JSON.stringify({
          artifact_id: ARTIFACT_ID,
          filename: 'sintetico.csv',
          byte_size: 20,
          zone: 'quarantine',
          status: 'quarantined',
          already_present: false,
          ignored: 'no se refleja',
        }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      ),
    );
    vi.stubGlobal('fetch', upstream);

    const response = await POST(
      request({ cookie: 'no-reenviar', referer: 'http://fincilia.test/privado' }),
      context(),
    );
    const payload = (await response.json()) as Record<string, unknown>;

    expect(response.status).toBe(200);
    expect(mocks.fetchSource).toHaveBeenCalledWith(
      'token-sintetico',
      COMPANY_ID,
      SOURCE_ID,
    );
    expect(upstream).toHaveBeenCalledOnce();
    const init = upstream.mock.calls[0]?.[1] as RequestInit;
    expect(init.headers).toEqual({
      accept: 'application/json',
      authorization: 'Bearer token-sintetico',
      'content-type': 'multipart/form-data; boundary=synthetic',
    });
    expect(payload).not.toHaveProperty('ignored');
    expect(payload).not.toHaveProperty('token');
    expect(payload.source_id).toBe(SOURCE_ID);
    expect(payload.next_href).toBe(
      `/empresas/${COMPANY_ID}/documentos/${ARTIFACT_ID}?fuente=${SOURCE_ID}`,
    );
  });

  it('no refleja el cuerpo upstream y limpia sesion ante 401', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response('detalle-interno-sintetico', { status: 401 }),
      ),
    );

    const response = await POST(request(), context());
    const payload = (await response.json()) as { detail: string };

    expect(response.status).toBe(401);
    expect(mocks.clearSession).toHaveBeenCalledOnce();
    expect(payload.detail).not.toContain('detalle-interno');
  });

  it('aborta y cancela el reenvio del cuerpo ante una respuesta temprana', async () => {
    const sourceCancelled = vi.fn();
    const sourceBody = new ReadableStream<Uint8Array>({
      pull(controller) {
        controller.enqueue(new TextEncoder().encode('synthetic-chunk'));
      },
      cancel: sourceCancelled,
    });
    let forwardedSignal: AbortSignal | null = null;
    let signalAborted = false;
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: unknown, init?: RequestInit) => {
        forwardedSignal = init?.signal ?? null;
        const forwardedBody = init?.body as ReadableStream<Uint8Array>;
        forwardedSignal?.addEventListener(
          'abort',
          () => {
            signalAborted = true;
            void forwardedBody.cancel();
          },
          { once: true },
        );
        return new Response('denied', { status: 401 });
      }),
    );
    const streamingRequest = new Request(URL, {
      method: 'POST',
      headers: {
        origin: 'http://fincilia.test',
        host: 'fincilia.test',
        'content-type': 'multipart/form-data; boundary=synthetic',
      },
      body: sourceBody,
      duplex: 'half',
    } as RequestInit & { duplex: 'half' });

    const response = await POST(streamingRequest, context());

    expect(response.status).toBe(401);
    expect(forwardedSignal).not.toBeNull();
    expect(signalAborted).toBe(true);
    await vi.waitFor(() => expect(sourceCancelled).toHaveBeenCalledOnce());
  });
});

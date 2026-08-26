import { NextResponse } from 'next/server';

import {
  EXPORT_TIMEOUT_MS,
  boundedExportStream,
  parseExportMetadata,
} from '@/lib/export-policy';
import { apiUrl } from '@/lib/server-config';
import { clearSession, readSession } from '@/lib/session';
import { isUuid } from '@/lib/upload-policy';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

type RouteContext = {
  params: Promise<{ companyId: string; datasetId: string }>;
};

function problem(status: number, code: string, detail: string): NextResponse {
  return NextResponse.json(
    { code, detail },
    {
      status,
      headers: {
        'cache-control': 'no-store',
        'x-content-type-options': 'nosniff',
      },
    },
  );
}

function publicUpstreamProblem(status: number): NextResponse {
  switch (status) {
    case 401:
      return problem(401, 'session-expired', 'La sesion vencio. Vuelve a ingresar.');
    case 403:
    case 404:
      return problem(403, 'access-denied', 'No tienes acceso a esta descarga.');
    case 409:
      return problem(
        409,
        'export-unavailable',
        'El conjunto ya no cumple las condiciones para exportarse.',
      );
    case 503:
      return problem(
        503,
        'service-unavailable',
        'La exportacion no esta disponible. Reintenta.',
      );
    default:
      return problem(502, 'upstream-failure', 'La descarga no se pudo iniciar.');
  }
}

export async function GET(
  request: Request,
  { params }: RouteContext,
): Promise<Response> {
  const session = await readSession();
  if (!session) {
    await clearSession();
    return publicUpstreamProblem(401);
  }

  const { companyId, datasetId } = await params;
  if (!isUuid(companyId) || !isUuid(datasetId)) {
    return problem(400, 'invalid-scope', 'Empresa o conjunto no valido.');
  }
  if (request.signal.aborted) {
    return problem(499, 'client-closed-request', 'La descarga fue cancelada.');
  }

  const upstreamController = new AbortController();
  const clientAborted = () => upstreamController.abort('client-aborted');
  request.signal.addEventListener('abort', clientAborted, { once: true });
  if (request.signal.aborted) {
    clientAborted();
  }
  const deadline = setTimeout(
    () => upstreamController.abort('export-timeout'),
    EXPORT_TIMEOUT_MS,
  );
  let cleaned = false;
  const cleanup = () => {
    if (!cleaned) {
      cleaned = true;
      clearTimeout(deadline);
      request.signal.removeEventListener('abort', clientAborted);
    }
  };

  let upstream: Response;
  try {
    upstream = await fetch(
      apiUrl(
        `/api/v1/companies/${encodeURIComponent(companyId)}/datasets/` +
          `${encodeURIComponent(datasetId)}/export`,
      ),
      {
        method: 'GET',
        cache: 'no-store',
        signal: upstreamController.signal,
        headers: {
          accept: 'text/csv',
          authorization: `Bearer ${session.token}`,
        },
      },
    );
  } catch {
    cleanup();
    if (request.signal.aborted || upstreamController.signal.reason === 'client-aborted') {
      return problem(499, 'client-closed-request', 'La descarga fue cancelada.');
    }
    if (upstreamController.signal.reason === 'export-timeout') {
      return problem(504, 'export-timeout', 'La descarga tardo demasiado. Reintenta.');
    }
    return publicUpstreamProblem(503);
  }

  if (!upstream.ok) {
    if (upstream.status === 401) {
      await clearSession();
    }
    try {
      await upstream.body?.cancel();
    } catch {
      /* cancelar es best-effort; el cuerpo nunca se refleja */
    }
    cleanup();
    return publicUpstreamProblem(upstream.status);
  }

  const metadata = parseExportMetadata(upstream.headers);
  if (metadata === null || upstream.body === null) {
    try {
      await upstream.body?.cancel();
    } catch {
      /* la respuesta publica no depende del fallo al cancelar */
    }
    upstreamController.abort('invalid-export-metadata');
    cleanup();
    return problem(
      502,
      'invalid-export-response',
      'La descarga recibio una respuesta invalida.',
    );
  }

  const stream = boundedExportStream(upstream.body, (reason) => {
    if (reason !== 'complete' && !upstreamController.signal.aborted) {
      upstreamController.abort(`export-${reason}`);
    }
    cleanup();
  });

  return new Response(stream, {
    status: 200,
    headers: {
      'content-type': metadata.contentType,
      'content-disposition': metadata.contentDisposition,
      'cache-control': 'private, no-store, max-age=0',
      pragma: 'no-cache',
      'x-content-type-options': 'nosniff',
      'x-fincilia-export-profile': metadata.profile,
      'x-fincilia-export-rows': String(metadata.rows),
      'x-fincilia-canonical-schema': metadata.canonicalSchema,
    },
  });
}

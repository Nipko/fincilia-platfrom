import { NextResponse } from 'next/server';

import { ApiError, fetchSource } from '@/lib/api';
import { apiUrl, publicWebOrigin } from '@/lib/server-config';
import { clearSession, readSession } from '@/lib/session';
import {
  MAX_UPLOAD_ENVELOPE_BYTES,
  UPLOAD_TIMEOUT_MS,
  isMultipart,
  isSameOrigin,
  isUuid,
  limitStream,
  parseContentLength,
  readBoundedJson,
  sanitizeArtifact,
} from '@/lib/upload-policy';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

type RouteContext = { params: Promise<{ companyId: string }> };
type DuplexRequestInit = RequestInit & { duplex: 'half' };

function problem(status: number, code: string, detail: string): NextResponse {
  return NextResponse.json(
    { code, detail },
    { status, headers: { 'cache-control': 'no-store' } },
  );
}

function publicUpstreamProblem(status: number): NextResponse {
  switch (status) {
    case 401:
      return problem(401, 'session-expired', 'La sesion vencio. Vuelve a ingresar.');
    case 403:
    case 404:
      return problem(403, 'access-denied', 'No tienes acceso vigente para esta carga.');
    case 413:
      return problem(413, 'file-too-large', 'El archivo supera el limite de 25 MiB.');
    case 415:
      return problem(415, 'unsupported-document', 'El formato no fue aceptado.');
    case 503:
      return problem(503, 'service-unavailable', 'El almacenamiento no esta disponible. Reintenta.');
    default:
      return problem(502, 'upstream-failure', 'La carga no se pudo completar.');
  }
}

export async function POST(
  request: Request,
  { params }: RouteContext,
): Promise<NextResponse> {
  if (
    !isSameOrigin(
      request.url,
      request.headers.get('origin'),
      request.headers.get('host'),
      publicWebOrigin(),
    )
  ) {
    return problem(403, 'origin-denied', 'La carga debe comenzar en Fincilia.');
  }

  const session = await readSession();
  if (!session) {
    await clearSession();
    return publicUpstreamProblem(401);
  }

  const { companyId } = await params;
  const sourceId = new URL(request.url).searchParams.get('sourceId');
  if (!isUuid(companyId) || !isUuid(sourceId)) {
    return problem(400, 'invalid-scope', 'Empresa o fuente no valida.');
  }

  const contentType = request.headers.get('content-type');
  if (!isMultipart(contentType)) {
    return problem(415, 'multipart-required', 'Selecciona un archivo para subir.');
  }
  if (request.body === null) {
    return problem(400, 'body-required', 'Selecciona un archivo para subir.');
  }
  if (request.signal.aborted) {
    return problem(499, 'client-closed-request', 'La carga fue cancelada.');
  }

  let declaredLength: number | null;
  try {
    declaredLength = parseContentLength(request.headers.get('content-length'));
  } catch {
    return problem(400, 'invalid-content-length', 'La longitud de la carga no es valida.');
  }
  if (declaredLength !== null && declaredLength > MAX_UPLOAD_ENVELOPE_BYTES) {
    return publicUpstreamProblem(413);
  }

  try {
    const source = await fetchSource(session.token, companyId, sourceId);
    if (source.status !== 'active') {
      return problem(409, 'inactive-source', 'La fuente elegida ya no esta activa.');
    }
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      await clearSession();
      return publicUpstreamProblem(401);
    }
    if (error instanceof ApiError && (error.status === 403 || error.status === 404)) {
      return publicUpstreamProblem(403);
    }
    if (error instanceof ApiError && error.status === 503) {
      return publicUpstreamProblem(503);
    }
    return problem(502, 'source-validation-failed', 'No se pudo validar la fuente.');
  }

  const upstreamController = new AbortController();
  const clientAborted = () => upstreamController.abort('client-aborted');
  request.signal.addEventListener('abort', clientAborted, { once: true });
  // AddEventListener no ejecuta retrospectivamente si la cancelacion ocurrio
  // mientras se validaba la fuente. Releer el estado cierra esa carrera.
  if (request.signal.aborted) {
    clientAborted();
  }
  if (upstreamController.signal.aborted) {
    request.signal.removeEventListener('abort', clientAborted);
    return problem(499, 'client-closed-request', 'La carga fue cancelada.');
  }
  const deadline = setTimeout(() => upstreamController.abort('upload-timeout'), UPLOAD_TIMEOUT_MS);
  const counted = limitStream(
    request.body,
    MAX_UPLOAD_ENVELOPE_BYTES,
    () => upstreamController.abort('upload-too-large'),
    upstreamController.signal,
  );

  let upstream: Response;
  const finish = (reason: string) => {
    // Una respuesta temprana del upstream no implica que Node deje de consumir
    // el request body. Abortar explicitamente cierra el reenvio antes de quitar
    // el deadline y el listener del cliente. Una razon previa nunca se pisa.
    if (!upstreamController.signal.aborted) {
      upstreamController.abort(reason);
    }
    clearTimeout(deadline);
    request.signal.removeEventListener('abort', clientAborted);
  };
  try {
    const init: DuplexRequestInit = {
      method: 'POST',
      duplex: 'half',
      cache: 'no-store',
      signal: upstreamController.signal,
      headers: {
        accept: 'application/json',
        authorization: `Bearer ${session.token}`,
        'content-type': contentType,
      },
      body: counted.stream,
    };
    upstream = await fetch(
      apiUrl(`/api/v1/companies/${encodeURIComponent(companyId)}/documents`),
      init,
    );
  } catch {
    finish('upload-failed');
    if (counted.exceeded()) {
      return publicUpstreamProblem(413);
    }
    if (request.signal.aborted) {
      return problem(499, 'client-closed-request', 'La carga fue cancelada.');
    }
    if (upstreamController.signal.reason === 'upload-timeout') {
      return problem(504, 'upload-timeout', 'La carga tardo demasiado. Reintenta.');
    }
    return publicUpstreamProblem(503);
  }

  if (!upstream.ok) {
    // No reflejar el cuerpo: puede ser ilegible o contener detalle no destinado
    // al navegador. El estado es suficiente para una respuesta segura y estable.
    if (upstream.status === 401) {
      await clearSession();
    }
    try {
      await upstream.body?.cancel();
    } catch {
      // Cancelar es best-effort; la respuesta publica depende solo del estado.
    }
    finish('upstream-rejected');
    return publicUpstreamProblem(upstream.status);
  }

  let artifact;
  try {
    artifact = sanitizeArtifact(await readBoundedJson(upstream.body));
  } catch {
    upstreamController.abort('invalid-upstream-response');
    finish('invalid-upstream-response');
    if (request.signal.aborted) {
      return problem(499, 'client-closed-request', 'La carga fue cancelada.');
    }
    if (upstreamController.signal.reason === 'upload-timeout') {
      return problem(504, 'upload-timeout', 'La carga tardo demasiado. Reintenta.');
    }
    return problem(502, 'invalid-upstream-response', 'La carga no se pudo confirmar.');
  }
  finish('upload-complete');
  if (artifact === null) {
    return problem(502, 'invalid-upstream-response', 'La carga no se pudo confirmar.');
  }

  const query = new URLSearchParams({ fuente: sourceId });
  return NextResponse.json(
    {
      ...artifact,
      source_id: sourceId,
      next_href:
        `/empresas/${encodeURIComponent(companyId)}/documentos/` +
        `${encodeURIComponent(artifact.artifact_id)}?${query.toString()}`,
    },
    { status: upstream.status, headers: { 'cache-control': 'no-store' } },
  );
}

import { NextResponse } from 'next/server';

import { apiUrl } from '@/lib/server-config';
import { clearSession, readSession } from '@/lib/session';
import { isUuid } from '@/lib/upload-policy';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const MAX_REPORT_BYTES = 1_048_576;

function problem(status: number, detail: string): NextResponse {
  return NextResponse.json({ detail }, { status, headers: {
    'cache-control': 'no-store', 'x-content-type-options': 'nosniff',
  }});
}

export async function GET(
  request: Request,
  { params }: { params: Promise<{ companyId: string }> },
): Promise<Response> {
  const session = await readSession();
  if (!session) return problem(401, 'La sesion vencio. Vuelve a ingresar.');
  const { companyId } = await params;
  if (!isUuid(companyId)) return problem(400, 'Empresa no valida.');

  const source = new URL(request.url);
  const days = source.searchParams.get('days') ?? '90';
  const asOf = source.searchParams.get('as_of');
  if (!['30', '90', '180', '365'].includes(days)
      || (asOf !== null && !/^\d{4}-\d{2}-\d{2}$/.test(asOf))) {
    return problem(400, 'Rango de informe no valido.');
  }
  const query = new URLSearchParams({ days });
  if (asOf) query.set('as_of', asOf);

  let upstream: Response;
  try {
    upstream = await fetch(apiUrl(
      `/api/v1/companies/${encodeURIComponent(companyId)}/reports/operational.csv?${query}`), {
      cache: 'no-store', signal: AbortSignal.timeout(15_000),
      headers: { accept: 'text/csv', authorization: `Bearer ${session.token}` },
    });
  } catch {
    return problem(503, 'El informe no esta disponible. Reintenta.');
  }
  if (!upstream.ok) {
    if (upstream.status === 401) await clearSession();
    return problem([401, 403, 422].includes(upstream.status) ? upstream.status : 502,
      upstream.status === 403 ? 'No tienes acceso a esta descarga.'
        : 'La descarga no se pudo generar.');
  }
  const declared = Number(upstream.headers.get('content-length') ?? '0');
  if (declared > MAX_REPORT_BYTES) return problem(502, 'El informe excedio el limite.');
  const body = new Uint8Array(await upstream.arrayBuffer());
  if (body.byteLength > MAX_REPORT_BYTES) return problem(502, 'El informe excedio el limite.');
  const disposition = upstream.headers.get('content-disposition');
  if (!disposition?.startsWith('attachment; filename="fincilia-informe-')) {
    return problem(502, 'La descarga recibio metadatos invalidos.');
  }
  return new Response(body, { status: 200, headers: {
    'content-type': 'text/csv; charset=utf-8',
    'content-disposition': disposition,
    'cache-control': 'private, no-store, max-age=0',
    'x-content-type-options': 'nosniff',
  }});
}

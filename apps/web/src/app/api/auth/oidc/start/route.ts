import { NextResponse } from 'next/server';

import {
  ManagedOidcConfigurationError,
  OIDC_TRANSACTION_COOKIE,
  createManagedOidcTransaction,
  managedAuthorizeUrl,
  managedOidcConfig,
  oidcTransactionCookieOptions,
  sealManagedOidcTransaction,
} from '@/lib/managed-oidc';
import { publicWebOrigin } from '@/lib/server-config';
import { isSameOrigin } from '@/lib/upload-policy';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
const MAX_FORM_BYTES = 1024;
const FORM_CONTENT_TYPE = /^application\/x-www-form-urlencoded(?:;\s*charset=utf-8)?$/i;

function problem(status: number, code: string, detail: string): NextResponse {
  return NextResponse.json({ code, detail }, {
    status, headers: { 'cache-control': 'no-store' },
  });
}

export async function POST(request: Request): Promise<NextResponse> {
  let origin: string | null;
  try {
    origin = publicWebOrigin();
  } catch {
    return problem(503, 'managed-sign-in-unavailable',
      'El ingreso administrado no esta disponible.');
  }
  if (!isSameOrigin(request.url, request.headers.get('origin'),
    request.headers.get('host'), origin)) {
    return problem(403, 'origin-denied', 'El ingreso debe comenzar en Fincilia.');
  }
  const contentType = request.headers.get('content-type') ?? '';
  const declaredHeader = request.headers.get('content-length');
  const declared = declaredHeader === null ? null : Number(declaredHeader);
  if (!FORM_CONTENT_TYPE.test(contentType) ||
      (declared !== null && (!Number.isSafeInteger(declared) ||
        declared < 0 || declared > MAX_FORM_BYTES))) {
    return problem(400, 'invalid-sign-in-request', 'El ingreso no se pudo iniciar.');
  }
  try {
    const config = managedOidcConfig();
    if (request.body === null) throw new TypeError('invalid managed sign-in input');
    const reader = request.body.getReader();
    const decoder = new TextDecoder('utf-8', { fatal: true });
    let bytes = 0;
    let encoded = '';
    try {
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        bytes += value.byteLength;
        if (bytes > MAX_FORM_BYTES) {
          await reader.cancel();
          throw new TypeError('invalid managed sign-in input');
        }
        encoded += decoder.decode(value, { stream: true });
      }
      encoded += decoder.decode();
    } finally {
      reader.releaseLock();
    }
    const form = new FormData();
    for (const [key, value] of new URLSearchParams(encoded)) form.append(key, value);
    const transaction = createManagedOidcTransaction(form);
    const response = NextResponse.redirect(managedAuthorizeUrl(transaction, config),
      { status: 303 });
    response.headers.set('cache-control', 'no-store');
    response.cookies.set(OIDC_TRANSACTION_COOKIE,
      sealManagedOidcTransaction(transaction, config.transactionKey),
      oidcTransactionCookieOptions());
    return response;
  } catch (error) {
    if (error instanceof ManagedOidcConfigurationError) {
      return problem(503, 'managed-sign-in-unavailable',
        'El ingreso administrado no esta disponible.');
    }
    return problem(422, 'invalid-sign-in-request',
      'Revisa los datos antes de continuar.');
  }
}

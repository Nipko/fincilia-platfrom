import { NextResponse } from 'next/server';

import {
  ManagedOidcConfigurationError,
  OIDC_CALLBACK_PATH,
  OIDC_TRANSACTION_COOKIE,
  managedLogoutUrl,
  managedOidcLogoutConfig,
} from '@/lib/managed-oidc';
import { publicWebOrigin } from '@/lib/server-config';
import { clearSessionFromResponse } from '@/lib/session';
import { isSameOrigin } from '@/lib/upload-policy';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

function clearBrowserState(response: NextResponse): NextResponse {
  clearSessionFromResponse(response);
  response.cookies.set(OIDC_TRANSACTION_COOKIE, '', {
    httpOnly: true,
    sameSite: 'lax',
    secure: process.env.FINCILIA_WEB_SECURE_COOKIES === 'true',
    path: OIDC_CALLBACK_PATH,
    maxAge: 0,
  });
  response.headers.set('cache-control', 'no-store');
  return response;
}

function problem(status: number, code: string): NextResponse {
  return NextResponse.json({
    code,
    detail: 'No pudimos cerrar la sesion administrada.',
  }, { status, headers: { 'cache-control': 'no-store' } });
}

export async function POST(request: Request): Promise<NextResponse> {
  let origin: string | null;
  try {
    origin = publicWebOrigin();
  } catch {
    return problem(503, 'managed-sign-out-unavailable');
  }
  if (!isSameOrigin(request.url, request.headers.get('origin'),
    request.headers.get('host'), origin)) {
    return problem(403, 'origin-denied');
  }

  try {
    const config = managedOidcLogoutConfig();
    return clearBrowserState(NextResponse.redirect(managedLogoutUrl(config), 303));
  } catch (error) {
    if (!(error instanceof ManagedOidcConfigurationError)) throw error;
    const fallback = origin ? new URL('/entrar?error=managed-unavailable', origin) : null;
    if (fallback === null) {
      return clearBrowserState(problem(503, 'managed-sign-out-unavailable'));
    }
    return clearBrowserState(NextResponse.redirect(fallback, 303));
  }
}

import type { NextRequest } from 'next/server';
import { NextResponse } from 'next/server';

import { ApiError, exchangeManagedIdentity } from '@/lib/api';
import {
  ManagedOidcConfigurationError,
  OIDC_CALLBACK_PATH,
  OIDC_TRANSACTION_COOKIE,
  exactState,
  managedOidcConfig,
  openManagedOidcTransaction,
} from '@/lib/managed-oidc';
import { publicWebOrigin } from '@/lib/server-config';
import { writeSessionToResponse } from '@/lib/session';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
const CODE = /^[A-Za-z0-9._~-]{16,2048}$/;

function finish(path: string): NextResponse {
  const origin = publicWebOrigin();
  if (origin === null) throw new ManagedOidcConfigurationError();
  const response = NextResponse.redirect(new URL(path, origin));
  response.headers.set('cache-control', 'no-store');
  response.cookies.set(OIDC_TRANSACTION_COOKIE, '', {
    httpOnly: true, sameSite: 'lax', secure: true,
    path: OIDC_CALLBACK_PATH, maxAge: 0,
  });
  return response;
}

export async function GET(request: NextRequest): Promise<NextResponse> {
  let config;
  try {
    config = managedOidcConfig();
  } catch (error) {
    if (error instanceof ManagedOidcConfigurationError) {
      const response = NextResponse.json(
        { code: 'managed-sign-in-unavailable',
          detail: 'El ingreso administrado no esta disponible.' },
        { status: 503, headers: { 'cache-control': 'no-store' } },
      );
      response.cookies.set(OIDC_TRANSACTION_COOKIE, '', {
        httpOnly: true, sameSite: 'lax', secure: true,
        path: OIDC_CALLBACK_PATH, maxAge: 0,
      });
      return response;
    }
    throw error;
  }
  const transaction = openManagedOidcTransaction(
    request.cookies.get(OIDC_TRANSACTION_COOKIE)?.value,
    config.transactionKey,
  );
  const code = request.nextUrl.searchParams.get('code') ?? '';
  const state = request.nextUrl.searchParams.get('state') ?? '';
  if (request.nextUrl.searchParams.has('error') || transaction === null ||
      !CODE.test(code) || !exactState(state, transaction.state)) {
    return finish('/entrar?error=managed-rejected');
  }
  try {
    const session = await exchangeManagedIdentity({
      code, verifier: transaction.verifier, nonce: transaction.nonce,
      ...(transaction.inviteCode ? { invite_code: transaction.inviteCode } : {}),
      ...(transaction.firmName ? { firm_name: transaction.firmName } : {}),
    });
    const response = finish('/empresas');
    writeSessionToResponse(response, session.token, session.display_name,
      session.expires_at);
    return response;
  } catch (error) {
    const retry = transaction.mode === 'register' ?
      '/registro?error=managed-registration' : '/entrar?error=managed-rejected';
    if (error instanceof ApiError) return finish(retry);
    return finish('/entrar?error=managed-unavailable');
  }
}

// @vitest-environment node

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { NextRequest } from 'next/server';

const mocks = vi.hoisted(() => ({
  exchange: vi.fn(),
  writeSession: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
  ApiError: class ApiError extends Error {
    code: string | null = null;
  },
  exchangeManagedIdentity: mocks.exchange,
}));
vi.mock('@/lib/session', () => ({ writeSessionToResponse: mocks.writeSession }));

import { GET } from '../route';
import {
  OIDC_TRANSACTION_COOKIE,
  createManagedOidcTransaction,
  managedOidcConfig,
  sealManagedOidcTransaction,
} from '@/lib/managed-oidc';

const KEY = Buffer.alloc(32, 11).toString('base64url');
const CODE = 'code_123456789012345678901234567890';

function configure() {
  vi.stubEnv('FINCILIA_OIDC_ENABLED', 'true');
  vi.stubEnv('FINCILIA_OIDC_REGISTRATION_MODE', 'public_google');
  vi.stubEnv('FINCILIA_PUBLIC_ORIGIN', 'https://pilot.fincilia.test');
  vi.stubEnv('FINCILIA_OIDC_AUTHORIZE_ENDPOINT',
    'https://auth.fincilia.test/oauth2/authorize');
  vi.stubEnv('FINCILIA_OIDC_REDIRECT_URI',
    'https://pilot.fincilia.test/api/auth/callback/cognito');
  vi.stubEnv('FINCILIA_OIDC_CLIENT_ID', 'public-client-123');
  vi.stubEnv('FINCILIA_OAUTH_TRANSACTION_KEY', KEY);
  vi.stubEnv('FINCILIA_WEB_SECURE_COOKIES', 'true');
}

function transaction() {
  const form = new FormData();
  form.set('mode', 'register');
  form.set('firmName', 'Firma Fincilia');
  form.set('acceptTerms', 'yes');
  form.set('acknowledgePrivacy', 'yes');
  return createManagedOidcTransaction(form);
}

function request(state: string, sealed: string) {
  return new NextRequest(
    `https://pilot.fincilia.test/api/auth/callback/cognito?code=${CODE}&state=${state}`,
    { headers: { cookie: `${OIDC_TRANSACTION_COOKIE}=${sealed}` } },
  );
}

describe('callback Cognito BFF', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.unstubAllEnvs();
    configure();
    mocks.exchange.mockResolvedValue({
      token: 'internal-session-token',
      display_name: 'Persona Piloto',
      expires_at: Math.floor(Date.now() / 1000) + 900,
    });
  });

  it('valida state y envia codigo y PKCE solo al API interno', async () => {
    const tx = transaction();
    const sealed = sealManagedOidcTransaction(tx, managedOidcConfig().transactionKey);
    const response = await GET(request(tx.state, sealed));

    expect(response.status).toBe(307);
    expect(response.headers.get('location')).toBe(
      'https://pilot.fincilia.test/empresas/nueva');
    expect(mocks.exchange).toHaveBeenCalledWith({
      code: CODE,
      verifier: tx.verifier,
      nonce: tx.nonce,
      mode: 'register',
      firm_name: tx.firmName,
      terms_version: 'terms-2026-09-03-en',
      privacy_version: 'privacy-2026-09-03-en',
    });
    expect(mocks.writeSession).toHaveBeenCalledOnce();
    const cookie = response.headers.get('set-cookie') ?? '';
    expect(cookie).toContain('fincilia_oidc_tx=');
    expect(cookie).toContain('Max-Age=0');
    expect(cookie).not.toContain(CODE);
  });

  it('state incorrecto borra la transaccion sin contactar el API', async () => {
    const tx = transaction();
    const sealed = sealManagedOidcTransaction(tx, managedOidcConfig().transactionKey);
    const response = await GET(request('x'.repeat(43), sealed));

    expect(response.headers.get('location')).toBe(
      'https://pilot.fincilia.test/entrar?error=managed-rejected');
    expect(mocks.exchange).not.toHaveBeenCalled();
    expect(mocks.writeSession).not.toHaveBeenCalled();
  });
});

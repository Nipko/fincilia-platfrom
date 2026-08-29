// @vitest-environment node

import { beforeEach, describe, expect, it, vi } from 'vitest';

import { POST } from '../route';

const KEY = Buffer.alloc(32, 9).toString('base64url');
const URL = 'https://pilot.fincilia.test/api/auth/oidc/start';

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

function request(body: URLSearchParams, origin = 'https://pilot.fincilia.test') {
  const encoded = body.toString();
  return new Request(URL, {
    method: 'POST',
    headers: {
      origin,
      host: 'pilot.fincilia.test',
      'content-type': 'application/x-www-form-urlencoded',
      'content-length': String(Buffer.byteLength(encoded)),
    },
    body: encoded,
  });
}

describe('inicio OIDC BFF', () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
    configure();
  });

  it('crea redireccion Google PKCE y cookie cifrada sin reflejar el alta', async () => {
    const body = new URLSearchParams({
      mode: 'register',
      firmName: 'Firma Fincilia',
      acceptTerms: 'yes',
      acknowledgePrivacy: 'yes',
    });
    const response = await POST(request(body));
    const location = response.headers.get('location') ?? '';
    const cookie = response.headers.get('set-cookie') ?? '';

    expect(response.status).toBe(303);
    expect(location).toContain('identity_provider=Google');
    expect(location).toContain('code_challenge_method=S256');
    expect(location).not.toContain('Firma');
    expect(cookie).toContain('fincilia_oidc_tx=');
    expect(cookie).toContain('HttpOnly');
    expect(cookie).toContain('Secure');
    expect(cookie).toContain('SameSite=lax');
    expect(cookie).not.toContain('Firma');
  });

  it('rechaza origen externo antes de crear una transaccion', async () => {
    const response = await POST(request(
      new URLSearchParams({ mode: 'login' }), 'https://evil.test'));
    expect(response.status).toBe(403);
    expect(response.headers.get('location')).toBeNull();
    expect(response.headers.get('set-cookie')).toBeNull();
  });

  it('exige firma, terminos y privacidad para una cuenta nueva', async () => {
    const response = await POST(request(new URLSearchParams({ mode: 'register' })));
    expect(response.status).toBe(422);
    expect(response.headers.get('location')).toBeNull();
  });

  it('limita el cuerpo real aunque el cliente omita content-length', async () => {
    const response = await POST(new Request(URL, {
      method: 'POST',
      headers: {
        origin: 'https://pilot.fincilia.test',
        host: 'pilot.fincilia.test',
        'content-type': 'application/x-www-form-urlencoded',
      },
      body: `mode=login&padding=${'x'.repeat(2048)}`,
    }));
    expect(response.status).toBe(422);
    expect(response.headers.get('set-cookie')).toBeNull();
  });

  it('una configuracion de origen invalida falla cerrada y sin redireccion', async () => {
    vi.stubEnv('FINCILIA_PUBLIC_ORIGIN', 'not-a-url');
    const response = await POST(request(new URLSearchParams({ mode: 'login' })));
    expect(response.status).toBe(503);
    expect(response.headers.get('location')).toBeNull();
  });
});

// @vitest-environment node

import { beforeEach, describe, expect, it, vi } from 'vitest';

import { POST } from '../route';

const REQUEST_URL = 'https://pilot.fincilia.test/api/auth/oidc/logout';

function configure() {
  vi.stubEnv('FINCILIA_OIDC_ENABLED', 'true');
  vi.stubEnv('FINCILIA_PUBLIC_ORIGIN', 'https://pilot.fincilia.test');
  vi.stubEnv('FINCILIA_OIDC_AUTHORIZE_ENDPOINT',
    'https://auth.fincilia.test/oauth2/authorize');
  vi.stubEnv('FINCILIA_OIDC_CLIENT_ID', 'public-client-123');
  vi.stubEnv('FINCILIA_WEB_SECURE_COOKIES', 'true');
}

function request(origin = 'https://pilot.fincilia.test') {
  return new Request(REQUEST_URL, {
    method: 'POST',
    headers: { origin, host: 'pilot.fincilia.test' },
  });
}

describe('cierre de sesion Cognito BFF', () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
    configure();
  });

  it('termina Hosted UI y elimina todas las cookies propias', async () => {
    const response = await POST(request());
    const location = new URL(response.headers.get('location') ?? '');
    const cookies = response.headers.getSetCookie().join('\n');

    expect(response.status).toBe(303);
    expect(location.origin + location.pathname).toBe('https://auth.fincilia.test/logout');
    expect(location.searchParams.get('client_id')).toBe('public-client-123');
    expect(location.searchParams.get('logout_uri')).toBe(
      'https://pilot.fincilia.test/entrar');
    expect([...location.searchParams.keys()].sort()).toEqual(['client_id', 'logout_uri']);
    expect(cookies).toContain('fincilia_session=');
    expect(cookies).toContain('fincilia_session_name=');
    expect(cookies).toContain('fincilia_oidc_tx=');
    expect(cookies.match(/Max-Age=0/g)).toHaveLength(3);
    expect(cookies).toContain('Secure');
    expect(response.headers.get('cache-control')).toBe('no-store');
  });

  it('rechaza logout CSRF sin borrar la sesion', async () => {
    const response = await POST(request('https://evil.test'));
    expect(response.status).toBe(403);
    expect(response.headers.get('location')).toBeNull();
    expect(response.headers.getSetCookie()).toHaveLength(0);
  });

  it('configuracion administrada incompleta borra local y vuelve a entrar', async () => {
    vi.stubEnv('FINCILIA_OIDC_CLIENT_ID', 'bad');
    const response = await POST(request());
    expect(response.status).toBe(303);
    expect(response.headers.get('location')).toBe(
      'https://pilot.fincilia.test/entrar?error=managed-unavailable');
    expect(response.headers.getSetCookie().join('\n')).toContain('fincilia_session=');
  });

  it('un origen publico ambiguo falla cerrado sin tocar cookies', async () => {
    vi.stubEnv('FINCILIA_PUBLIC_ORIGIN', 'https://pilot.fincilia.test/path');
    const response = await POST(request());
    expect(response.status).toBe(503);
    expect(response.headers.getSetCookie()).toHaveLength(0);
  });
});

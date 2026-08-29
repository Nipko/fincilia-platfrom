// @vitest-environment node

import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  ManagedOidcConfigurationError,
  createManagedOidcTransaction,
  exactState,
  managedAuthorizeUrl,
  managedLogoutUrl,
  managedOidcConfig,
  managedOidcLogoutConfig,
  openManagedOidcTransaction,
  sealManagedOidcTransaction,
} from '../managed-oidc';

const NOW = 1_788_000_000;
const KEY = Buffer.alloc(32, 7).toString('base64url');

function configure() {
  vi.stubEnv('FINCILIA_OIDC_ENABLED', 'true');
  vi.stubEnv('FINCILIA_PUBLIC_ORIGIN', 'https://pilot.fincilia.test');
  vi.stubEnv('FINCILIA_OIDC_AUTHORIZE_ENDPOINT',
    'https://auth.fincilia.test/oauth2/authorize');
  vi.stubEnv('FINCILIA_OIDC_REDIRECT_URI',
    'https://pilot.fincilia.test/api/auth/callback/cognito');
  vi.stubEnv('FINCILIA_OIDC_CLIENT_ID', 'public-client-123');
  vi.stubEnv('FINCILIA_OAUTH_TRANSACTION_KEY', KEY);
  vi.stubEnv('FINCILIA_WEB_SECURE_COOKIES', 'true');
}

function registration(): FormData {
  const form = new FormData();
  form.set('mode', 'register');
  form.set('inviteCode', 'Invite_code_12345678901234567890');
  form.set('firmName', 'Firma Privada Piloto');
  form.set('acceptTerms', 'yes');
  return form;
}

describe('transaccion OIDC administrada', () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
    configure();
  });

  it('cifra invitacion, firma, nonce, state y PKCE en una cookie acotada', () => {
    const config = managedOidcConfig();
    const transaction = createManagedOidcTransaction(registration(), NOW);
    const sealed = sealManagedOidcTransaction(transaction, config.transactionKey);

    expect(sealed).not.toContain('Invite_code');
    expect(sealed).not.toContain('Firma Privada');
    expect(transaction.state).toHaveLength(43);
    expect(transaction.nonce).toHaveLength(43);
    expect(transaction.verifier.length).toBeGreaterThanOrEqual(43);
    expect(openManagedOidcTransaction(sealed, config.transactionKey, NOW))
      .toEqual(transaction);
  });

  it('rechaza alteracion, vencimiento y state de longitud distinta', () => {
    const config = managedOidcConfig();
    const transaction = createManagedOidcTransaction(registration(), NOW);
    const sealed = sealManagedOidcTransaction(transaction, config.transactionKey);
    const mutated = `${sealed.slice(0, -1)}${sealed.endsWith('a') ? 'b' : 'a'}`;

    expect(openManagedOidcTransaction(mutated, config.transactionKey, NOW)).toBeNull();
    expect(openManagedOidcTransaction(sealed, config.transactionKey, NOW + 601)).toBeNull();
    expect(exactState(transaction.state, transaction.state)).toBe(true);
    expect(exactState('short', transaction.state)).toBe(false);
  });

  it('construye Code+PKCE con scopes minimos sin datos de alta en la URL', () => {
    const config = managedOidcConfig();
    const transaction = createManagedOidcTransaction(registration(), NOW);
    const url = new URL(managedAuthorizeUrl(transaction, config));

    expect(url.origin + url.pathname).toBe(
      'https://auth.fincilia.test/oauth2/authorize');
    expect(url.searchParams.get('response_type')).toBe('code');
    expect(url.searchParams.get('scope')).toBe('openid email profile');
    expect(url.searchParams.get('identity_provider')).toBe('Google');
    expect(url.searchParams.get('code_challenge_method')).toBe('S256');
    expect(url.search).not.toContain('Invite_code');
    expect(url.search).not.toContain('Firma');
  });

  it('construye logout Cognito con parametros exactos y sin entrada del cliente', () => {
    const url = new URL(managedLogoutUrl(managedOidcLogoutConfig()));
    expect(url.origin + url.pathname).toBe('https://auth.fincilia.test/logout');
    expect(url.searchParams.get('client_id')).toBe('public-client-123');
    expect(url.searchParams.get('logout_uri')).toBe(
      'https://pilot.fincilia.test/entrar');
    expect([...url.searchParams.keys()].sort()).toEqual(['client_id', 'logout_uri']);
  });

  it('falla cerrado con HTTP, callback de otro origen o cookie insegura', () => {
    const mutations: Array<() => void> = [
      () => vi.stubEnv('FINCILIA_PUBLIC_ORIGIN', 'http://pilot.fincilia.test'),
      () => vi.stubEnv('FINCILIA_OIDC_REDIRECT_URI',
        'https://otro.fincilia.test/api/auth/callback/cognito'),
      () => vi.stubEnv('FINCILIA_WEB_SECURE_COOKIES', 'false'),
    ];
    for (const mutate of mutations) {
      vi.unstubAllEnvs();
      configure();
      mutate();
      expect(() => managedOidcConfig()).toThrow(ManagedOidcConfigurationError);
    }
  });
});

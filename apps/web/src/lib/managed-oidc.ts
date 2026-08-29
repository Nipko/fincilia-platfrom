import 'server-only';

import {
  createCipheriv,
  createDecipheriv,
  createHash,
  randomBytes,
  timingSafeEqual,
} from 'node:crypto';

import { publicWebOrigin } from './server-config';

export const OIDC_TRANSACTION_COOKIE = 'fincilia_oidc_tx';
export const OIDC_CALLBACK_PATH = '/api/auth/callback/cognito';
export const OIDC_TRANSACTION_TTL_SECONDS = 600;

const SAFE_VALUE = /^[A-Za-z0-9._~-]+$/;
const CONTROL = /[\u0000-\u001f\u007f]/;

export type ManagedOidcMode = 'login' | 'register';

export type ManagedOidcTransaction = {
  mode: ManagedOidcMode;
  state: string;
  nonce: string;
  verifier: string;
  inviteCode: string | null;
  firmName: string | null;
  expiresAt: number;
};

type ManagedOidcConfig = {
  authorizeEndpoint: string;
  clientId: string;
  redirectUri: string;
  transactionKey: Buffer;
};

export type ManagedOidcLogoutConfig = {
  clientId: string;
  logoutEndpoint: string;
  logoutUri: string;
};

export class ManagedOidcConfigurationError extends Error {
  constructor() {
    super('managed identity is not safely configured');
    this.name = 'ManagedOidcConfigurationError';
  }
}

export function managedOidcEnabled(): boolean {
  return process.env.FINCILIA_OIDC_ENABLED === 'true';
}

function exactHttpsUrl(value: string | undefined, expectedPath?: string): URL {
  if (!value) throw new ManagedOidcConfigurationError();
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    throw new ManagedOidcConfigurationError();
  }
  if (
    parsed.protocol !== 'https:' || parsed.username !== '' || parsed.password !== '' ||
    parsed.search !== '' || parsed.hash !== '' ||
    (expectedPath !== undefined && parsed.pathname !== expectedPath)
  ) {
    throw new ManagedOidcConfigurationError();
  }
  return parsed;
}

export function managedOidcConfig(): ManagedOidcConfig {
  const logout = managedOidcLogoutConfig();
  const authorize = exactHttpsUrl(
    process.env.FINCILIA_OIDC_AUTHORIZE_ENDPOINT,
    '/oauth2/authorize',
  );
  const redirect = exactHttpsUrl(
    process.env.FINCILIA_OIDC_REDIRECT_URI,
    OIDC_CALLBACK_PATH,
  );
  const origin = publicWebOrigin();
  if (redirect.origin !== origin) throw new ManagedOidcConfigurationError();
  const encodedKey = process.env.FINCILIA_OAUTH_TRANSACTION_KEY;
  if (!encodedKey || !/^[A-Za-z0-9_-]{43}$/.test(encodedKey)) {
    throw new ManagedOidcConfigurationError();
  }
  const transactionKey = Buffer.from(encodedKey, 'base64url');
  if (transactionKey.length !== 32 || process.env.FINCILIA_WEB_SECURE_COOKIES !== 'true') {
    throw new ManagedOidcConfigurationError();
  }
  return {
    authorizeEndpoint: authorize.toString(),
    clientId: logout.clientId,
    redirectUri: redirect.toString(),
    transactionKey,
  };
}

export function managedOidcLogoutConfig(): ManagedOidcLogoutConfig {
  if (!managedOidcEnabled()) throw new ManagedOidcConfigurationError();
  const origin = publicWebOrigin();
  if (!origin || !origin.startsWith('https://') ||
      process.env.FINCILIA_WEB_SECURE_COOKIES !== 'true') {
    throw new ManagedOidcConfigurationError();
  }
  const authorize = exactHttpsUrl(
    process.env.FINCILIA_OIDC_AUTHORIZE_ENDPOINT,
    '/oauth2/authorize',
  );
  const clientId = process.env.FINCILIA_OIDC_CLIENT_ID;
  if (!clientId || clientId.length < 8 || clientId.length > 128 ||
      !SAFE_VALUE.test(clientId)) {
    throw new ManagedOidcConfigurationError();
  }
  return {
    clientId,
    logoutEndpoint: new URL('/logout', authorize.origin).toString(),
    logoutUri: new URL('/entrar', origin).toString(),
  };
}

export function managedLogoutUrl(config: ManagedOidcLogoutConfig): string {
  const url = new URL(config.logoutEndpoint);
  url.search = new URLSearchParams({
    client_id: config.clientId,
    logout_uri: config.logoutUri,
  }).toString();
  return url.toString();
}

function bounded(value: FormDataEntryValue | null, minimum: number, maximum: number): string {
  if (typeof value !== 'string') throw new TypeError('invalid managed sign-in input');
  const clean = value.trim().replace(/\s+/g, ' ');
  if (clean.length < minimum || clean.length > maximum || CONTROL.test(clean)) {
    throw new TypeError('invalid managed sign-in input');
  }
  return clean;
}

export function createManagedOidcTransaction(
  form: FormData,
  now = Math.floor(Date.now() / 1000),
): ManagedOidcTransaction {
  const mode = form.get('mode');
  if (mode !== 'login' && mode !== 'register') {
    throw new TypeError('invalid managed sign-in input');
  }
  let inviteCode: string | null = null;
  let firmName: string | null = null;
  const keys = [...form.keys()];
  const allowed = mode === 'register' ?
    new Set(['mode', 'inviteCode', 'firmName', 'acceptTerms']) : new Set(['mode']);
  if (keys.length !== new Set(keys).size || keys.some((key) => !allowed.has(key))) {
    throw new TypeError('invalid managed sign-in input');
  }
  if (mode === 'register') {
    inviteCode = bounded(form.get('inviteCode'), 24, 128);
    if (!SAFE_VALUE.test(inviteCode)) throw new TypeError('invalid managed sign-in input');
    firmName = bounded(form.get('firmName'), 2, 300);
    if (form.get('acceptTerms') !== 'yes') throw new TypeError('invalid managed sign-in input');
  }
  return {
    mode,
    state: randomBytes(32).toString('base64url'),
    nonce: randomBytes(32).toString('base64url'),
    verifier: randomBytes(64).toString('base64url'),
    inviteCode,
    firmName,
    expiresAt: now + OIDC_TRANSACTION_TTL_SECONDS,
  };
}

function transactionShape(value: unknown, now: number): value is ManagedOidcTransaction {
  if (!value || typeof value !== 'object') return false;
  const tx = value as Partial<ManagedOidcTransaction>;
  return (
    (tx.mode === 'login' || tx.mode === 'register') &&
    typeof tx.state === 'string' && tx.state.length === 43 && SAFE_VALUE.test(tx.state) &&
    typeof tx.nonce === 'string' && tx.nonce.length === 43 && SAFE_VALUE.test(tx.nonce) &&
    typeof tx.verifier === 'string' && tx.verifier.length >= 43 &&
    tx.verifier.length <= 128 && SAFE_VALUE.test(tx.verifier) &&
    (tx.inviteCode === null || (typeof tx.inviteCode === 'string' &&
      tx.inviteCode.length >= 24 && tx.inviteCode.length <= 128 && SAFE_VALUE.test(tx.inviteCode))) &&
    (tx.firmName === null || (typeof tx.firmName === 'string' &&
      tx.firmName.length >= 2 && tx.firmName.length <= 300 && !CONTROL.test(tx.firmName))) &&
    typeof tx.expiresAt === 'number' && Number.isInteger(tx.expiresAt) &&
    tx.expiresAt >= now && tx.expiresAt <= now + OIDC_TRANSACTION_TTL_SECONDS
  );
}

export function sealManagedOidcTransaction(
  transaction: ManagedOidcTransaction,
  key: Buffer,
): string {
  const iv = randomBytes(12);
  const cipher = createCipheriv('aes-256-gcm', key, iv);
  cipher.setAAD(Buffer.from(OIDC_TRANSACTION_COOKIE, 'utf8'));
  const ciphertext = Buffer.concat([
    cipher.update(JSON.stringify(transaction), 'utf8'), cipher.final(),
  ]);
  const tag = cipher.getAuthTag();
  return ['v1', iv.toString('base64url'), ciphertext.toString('base64url'),
    tag.toString('base64url')].join('.');
}

export function openManagedOidcTransaction(
  sealed: string | undefined,
  key: Buffer,
  now = Math.floor(Date.now() / 1000),
): ManagedOidcTransaction | null {
  if (!sealed || sealed.length > 2048) return null;
  const parts = sealed.split('.');
  if (parts.length !== 4 || parts[0] !== 'v1') return null;
  try {
    const encoded = parts.slice(1);
    if (encoded.some((part) => !part || !/^[A-Za-z0-9_-]+$/.test(part))) return null;
    const [iv, ciphertext, tag] = encoded.map((part) => Buffer.from(part, 'base64url'));
    if (!iv || !ciphertext || !tag ||
        iv.toString('base64url') !== encoded[0] ||
        ciphertext.toString('base64url') !== encoded[1] ||
        tag.toString('base64url') !== encoded[2]) return null;
    if (iv.length !== 12 || tag.length !== 16 || ciphertext.length > 1536) return null;
    const decipher = createDecipheriv('aes-256-gcm', key, iv);
    decipher.setAAD(Buffer.from(OIDC_TRANSACTION_COOKIE, 'utf8'));
    decipher.setAuthTag(tag);
    const plaintext = Buffer.concat([decipher.update(ciphertext), decipher.final()]);
    const value: unknown = JSON.parse(plaintext.toString('utf8'));
    return transactionShape(value, now) ? value : null;
  } catch {
    return null;
  }
}

export function managedAuthorizeUrl(
  transaction: ManagedOidcTransaction,
  config: ManagedOidcConfig,
): string {
  const challenge = createHash('sha256')
    .update(transaction.verifier, 'ascii').digest('base64url');
  const url = new URL(config.authorizeEndpoint);
  url.search = new URLSearchParams({
    response_type: 'code', client_id: config.clientId, redirect_uri: config.redirectUri,
    scope: 'openid email profile', state: transaction.state, nonce: transaction.nonce,
    code_challenge: challenge, code_challenge_method: 'S256',
    identity_provider: 'Google', prompt: 'select_account',
  }).toString();
  return url.toString();
}

export function exactState(received: string, expected: string): boolean {
  if (received.length !== expected.length) return false;
  return timingSafeEqual(Buffer.from(received), Buffer.from(expected));
}

export function oidcTransactionCookieOptions() {
  return {
    httpOnly: true, sameSite: 'lax', secure: true,
    path: OIDC_CALLBACK_PATH, maxAge: OIDC_TRANSACTION_TTL_SECONDS,
  } as const;
}

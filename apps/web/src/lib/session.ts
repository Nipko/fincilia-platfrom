/**
 * Sesion del navegador: una cookie `httpOnly` con el token y nada mas.
 *
 * `httpOnly` para que ningun script la lea, `sameSite: strict` para que no viaje
 * en peticiones que origine otro sitio, y una caducidad que copia la del token
 * en vez de inventar una propia: dos relojes distintos acaban discrepando.
 */

import { cookies } from 'next/headers';
import type { NextResponse } from 'next/server';

export const SESSION_COOKIE = 'fincilia_session';

export type StoredSession = {
  token: string;
  displayName: string;
};

export async function readSession(): Promise<StoredSession | null> {
  const store = await cookies();
  const token = store.get(SESSION_COOKIE)?.value;
  const displayName = store.get(`${SESSION_COOKIE}_name`)?.value;
  if (!token) {
    return null;
  }
  return { token, displayName: displayName ?? 'Sesion activa' };
}

export async function writeSession(
  token: string,
  displayName: string,
  expiresAt: number,
): Promise<void> {
  const store = await cookies();
  const maxAge = Math.max(0, expiresAt - Math.floor(Date.now() / 1000));
  const common = {
    httpOnly: true,
    sameSite: 'strict',
    // `secure` solo si el origen es https: en el stack local es http, y una
    // cookie `secure` sobre http simplemente no se guarda.
    secure: process.env.FINCILIA_WEB_SECURE_COOKIES === 'true',
    path: '/',
    maxAge,
  } as const;
  store.set(SESSION_COOKIE, token, common);
  // El nombre visible no es un secreto y se guarda aparte para no tener que
  // abrir el token en el servidor solo para saludar a alguien.
  store.set(`${SESSION_COOKIE}_name`, displayName, { ...common, httpOnly: false });
}

export function writeSessionToResponse(
  response: NextResponse,
  token: string,
  displayName: string,
  expiresAt: number,
): void {
  const maxAge = Math.max(0, expiresAt - Math.floor(Date.now() / 1000));
  const common = {
    httpOnly: true,
    sameSite: 'strict',
    secure: process.env.FINCILIA_WEB_SECURE_COOKIES === 'true',
    path: '/',
    maxAge,
  } as const;
  response.cookies.set(SESSION_COOKIE, token, common);
  response.cookies.set(`${SESSION_COOKIE}_name`, displayName, {
    ...common,
    httpOnly: false,
  });
}

export async function clearSession(): Promise<void> {
  const store = await cookies();
  store.delete(SESSION_COOKIE);
  store.delete(`${SESSION_COOKIE}_name`);
}

export function clearSessionFromResponse(response: NextResponse): void {
  const common = {
    httpOnly: true,
    sameSite: 'strict',
    secure: process.env.FINCILIA_WEB_SECURE_COOKIES === 'true',
    path: '/',
    maxAge: 0,
  } as const;
  response.cookies.set(SESSION_COOKIE, '', common);
  response.cookies.set(`${SESSION_COOKIE}_name`, '', {
    ...common,
    httpOnly: false,
  });
}

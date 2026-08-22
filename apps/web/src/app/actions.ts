'use server';

/**
 * Acciones de servidor. El formulario no llama a la API: llama aqui, y este
 * proceso llama a la API. Asi el token nunca cruza al navegador.
 */

import { redirect } from 'next/navigation';

import { ApiError, signIn } from '@/lib/api';
import { clearSession, writeSession } from '@/lib/session';

export type SignInState = { error: string | null };

export async function signInAction(
  _previous: SignInState,
  formData: FormData,
): Promise<SignInState> {
  const username = String(formData.get('username') ?? '').trim();
  const secret = String(formData.get('secret') ?? '');
  if (!username || !secret) {
    return { error: 'Escribe usuario y contrasena.' };
  }

  let session;
  try {
    session = await signIn(username, secret);
  } catch (error) {
    if (error instanceof ApiError && error.status === 429) {
      return { error: 'Demasiados intentos. Espera unos minutos.' };
    }
    if (error instanceof ApiError && error.status === 503) {
      return { error: 'La API no responde. Comprueba que el stack esta arriba.' };
    }
    // Un unico mensaje para usuario inexistente y contrasena incorrecta: la
    // interfaz no puede ser mas informativa que la API a proposito.
    return { error: 'Usuario o contrasena incorrectos.' };
  }

  await writeSession(session.token, session.display_name, session.expires_at);
  redirect('/empresas');
}

export async function signOutAction(): Promise<void> {
  await clearSession();
  redirect('/entrar');
}

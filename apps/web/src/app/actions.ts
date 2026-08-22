'use server';

/**
 * Acciones de servidor. El formulario no llama a la API: llama aqui, y este
 * proceso llama a la API. Asi el token nunca cruza al navegador.
 */

import { revalidatePath } from 'next/cache';
import { redirect } from 'next/navigation';

import { ApiError, signIn, uploadDocument } from '@/lib/api';
import { clearSession, readSession, writeSession } from '@/lib/session';

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

export type UploadState = { error: string | null; uploaded: string | null };

export async function uploadDocumentAction(
  _previous: UploadState,
  formData: FormData,
): Promise<UploadState> {
  const session = await readSession();
  if (!session) {
    redirect('/entrar');
  }
  const companyId = String(formData.get('companyId') ?? '');
  const file = formData.get('file');
  if (!(file instanceof File) || file.size === 0) {
    return { error: 'Elige un fichero.', uploaded: null };
  }

  let artifact;
  try {
    artifact = await uploadDocument(session.token, companyId, file);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      redirect('/entrar');
    }
    if (error instanceof ApiError && error.status === 403) {
      return { error: 'Este rol no puede subir documentos.', uploaded: null };
    }
    if (error instanceof ApiError && (error.status === 413 || error.status === 415)) {
      // El detalle viene de la API y ya esta escrito para no filtrar nada; se
      // pasa tal cual porque explica exactamente por que no se admitio.
      return { error: error.message, uploaded: null };
    }
    return { error: 'No se pudo subir el fichero.', uploaded: null };
  }

  revalidatePath(`/empresas/${companyId}`);
  const summary =
    artifact.zone === 'quarantine'
      ? `${artifact.filename} quedo en cuarentena: se detecto informacion sensible.`
      : artifact.already_present
        ? `${artifact.filename} ya estaba: los mismos bytes son la misma entrega.`
        : `${artifact.filename} almacenado.`;
  return { error: null, uploaded: summary };
}

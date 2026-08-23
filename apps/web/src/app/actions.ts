'use server';

/**
 * Acciones de servidor. El formulario no llama a la API: llama aqui, y este
 * proceso llama a la API. Asi el token nunca cruza al navegador.
 */

import { revalidatePath } from 'next/cache';
import { redirect } from 'next/navigation';

import {
  ApiError,
  type Blocker,
  createMapping,
  decideAmbiguity,
  prepareDataset,
  publishDataset,
  signIn,
  uploadDocument,
  validateMapping,
} from '@/lib/api';
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


// --------------------------------------------------------------------------- //
// Mapeo, preparacion y publicacion (FNC-P3)
// --------------------------------------------------------------------------- //

/**
 * Ninguna de estas acciones decide nada. Comprueban la forma del formulario para
 * no mandar basura, y cualquier otra cosa la decide la API: si responde 403, la
 * web lo ensena. Una segunda copia de la matriz de permisos aqui acabaria discrepando
 * de la del servidor, y la discrepancia siempre se descubre tarde.
 */

export type MappingState = {
  error: string | null;
  mappingVersionId: string | null;
  blockers: Blocker[];
};

/** Campos canonicos que la pantalla deja asignar a una columna. */
const FIELDS = [
  'occurred_on',
  'description',
  'reference',
  'amount',
  'debit',
  'credit',
  'direction',
] as const;

function readColumns(formData: FormData): Record<string, number> {
  const columns: Record<string, number> = {};
  for (const field of FIELDS) {
    const raw = String(formData.get(`col_${field}`) ?? '').trim();
    if (raw === '') {
      // Sin columna asignada. Ausente no es lo mismo que cero: la columna cero
      // es la primera del fichero.
      continue;
    }
    const index = Number.parseInt(raw, 10);
    if (Number.isInteger(index) && index >= 0) {
      columns[field] = index;
    }
  }
  return columns;
}

export async function createMappingAction(
  _previous: MappingState,
  formData: FormData,
): Promise<MappingState> {
  const session = await readSession();
  if (!session) {
    redirect('/entrar');
  }
  const companyId = String(formData.get('companyId') ?? '');
  const artifactId = String(formData.get('artifactId') ?? '');
  const dataSourceId = String(formData.get('dataSourceId') ?? '');
  const columns = readColumns(formData);
  if (!columns.occurred_on && columns.occurred_on !== 0) {
    return {
      error: 'Elige que columna lleva la fecha: un movimiento siempre tiene una.',
      mappingVersionId: null,
      blockers: [],
    };
  }
  if (!columns.description && columns.description !== 0) {
    return {
      error: 'Elige que columna lleva la descripcion.',
      mappingVersionId: null,
      blockers: [],
    };
  }

  let created;
  try {
    created = await createMapping(session.token, companyId, {
      artifact_id: artifactId,
      data_source_id: dataSourceId,
      display_name:
        String(formData.get('displayName') ?? '').trim() || 'Mapeo sin nombre',
      columns,
      date_format: String(formData.get('dateFormat') ?? 'iso'),
      decimal_format: String(formData.get('decimalFormat') ?? 'dot'),
      currency: String(formData.get('currency') ?? 'COP').toUpperCase(),
      direction_mode: String(formData.get('directionMode') ?? 'signed_amount'),
      header_row: Number.parseInt(String(formData.get('headerRow') ?? '1'), 10) || 1,
      first_data_row:
        Number.parseInt(String(formData.get('firstDataRow') ?? '2'), 10) || 2,
      ignored_columns: [],
    });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      redirect('/entrar');
    }
    if (error instanceof ApiError && error.status === 403) {
      return {
        error: 'Este rol no puede mapear columnas.',
        mappingVersionId: null,
        blockers: [],
      };
    }
    return {
      error:
        error instanceof ApiError ? error.message : 'No se pudo guardar el mapeo.',
      mappingVersionId: null,
      blockers: [],
    };
  }

  revalidatePath(`/empresas/${companyId}/documentos/${artifactId}/mapeo`);
  return {
    error: null,
    mappingVersionId: created.mapping_version_id,
    blockers: created.blockers,
  };
}

export type DecisionState = { error: string | null; resolved: string | null };

export async function decideAmbiguityAction(
  _previous: DecisionState,
  formData: FormData,
): Promise<DecisionState> {
  const session = await readSession();
  if (!session) {
    redirect('/entrar');
  }
  const companyId = String(formData.get('companyId') ?? '');
  const artifactId = String(formData.get('artifactId') ?? '');
  const mappingVersionId = String(formData.get('mappingVersionId') ?? '');
  const rationale = String(formData.get('rationale') ?? '').trim();
  if (rationale.length < 3) {
    // El motivo no es burocracia: dentro de un ano es lo unico que explica por
    // que este extracto se leyo dd/mm y el del mes siguiente no.
    return { error: 'Escribe por que eliges esto.', resolved: null };
  }

  try {
    await decideAmbiguity(session.token, companyId, mappingVersionId, {
      ambiguity_kind: String(formData.get('ambiguityKind') ?? ''),
      subject_ref: String(formData.get('subjectRef') ?? ''),
      resolved_value: String(formData.get('resolvedValue') ?? ''),
      rationale,
    });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      redirect('/entrar');
    }
    return {
      error:
        error instanceof ApiError
          ? error.message
          : 'No se pudo registrar la decision.',
      resolved: null,
    };
  }

  revalidatePath(`/empresas/${companyId}/documentos/${artifactId}/mapeo`);
  return { error: null, resolved: String(formData.get('subjectRef') ?? '') };
}

export type PrepareState = {
  error: string | null;
  datasetVersionId: string | null;
  summary: string | null;
  rejections: { record_ordinal: number; code: string; detail: string }[];
};

export async function prepareDatasetAction(
  _previous: PrepareState,
  formData: FormData,
): Promise<PrepareState> {
  const session = await readSession();
  if (!session) {
    redirect('/entrar');
  }
  const companyId = String(formData.get('companyId') ?? '');
  const artifactId = String(formData.get('artifactId') ?? '');
  const mappingVersionId = String(formData.get('mappingVersionId') ?? '');
  const accountId = String(formData.get('financialAccountId') ?? '');
  if (!accountId) {
    return {
      error: 'Elige contra que cuenta se registran estos movimientos.',
      datasetVersionId: null,
      summary: null,
      rejections: [],
    };
  }

  try {
    await validateMapping(session.token, companyId, mappingVersionId);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      redirect('/entrar');
    }
    return {
      error:
        error instanceof ApiError
          ? error.message
          : 'El mapeo no se pudo validar.',
      datasetVersionId: null,
      summary: null,
      rejections: [],
    };
  }

  let prepared;
  try {
    prepared = await prepareDataset(session.token, companyId, {
      artifact_id: artifactId,
      mapping_version_id: mappingVersionId,
      financial_account_id: accountId,
    });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      redirect('/entrar');
    }
    return {
      error:
        error instanceof ApiError
          ? error.message
          : 'No se pudo preparar el conjunto.',
      datasetVersionId: null,
      summary: null,
      rejections: [],
    };
  }

  revalidatePath(`/empresas/${companyId}/documentos/${artifactId}/mapeo`);
  const reused = prepared.reused ? ' Ya estaba preparado: no se duplico nada.' : '';
  return {
    error: null,
    datasetVersionId: prepared.dataset_version_id,
    summary:
      `${prepared.movement_count} movimiento(s) de ${prepared.record_count} fila(s)` +
      `, ${prepared.rejected_count} rechazada(s).${reused}` +
      ' Publicarlo es de otra persona.',
    rejections: prepared.rejections,
  };
}

export type PublishState = { error: string | null; published: string | null };

export async function publishDatasetAction(
  _previous: PublishState,
  formData: FormData,
): Promise<PublishState> {
  const session = await readSession();
  if (!session) {
    redirect('/entrar');
  }
  const companyId = String(formData.get('companyId') ?? '');
  const artifactId = String(formData.get('artifactId') ?? '');
  const datasetVersionId = String(formData.get('datasetVersionId') ?? '');

  let published;
  try {
    published = await publishDataset(session.token, companyId, datasetVersionId);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      redirect('/entrar');
    }
    if (error instanceof ApiError && error.status === 403) {
      return {
        error: 'Este rol no puede publicar conjuntos canonicos.',
        published: null,
      };
    }
    if (error instanceof ApiError && error.status === 409) {
      return {
        error:
          'Quien preparo esta version no puede publicarla. Tiene que revisarla ' +
          'otra persona.',
        published: null,
      };
    }
    return {
      error:
        error instanceof ApiError ? error.message : 'No se pudo publicar.',
      published: null,
    };
  }

  revalidatePath(`/empresas/${companyId}/documentos/${artifactId}/mapeo`);
  return {
    error: null,
    published:
      `Publicado con ${published.movement_count} movimiento(s), motor ` +
      `${published.engine_release}. Reprocesar creara otra version y esta se ` +
      'conserva.',
  };
}

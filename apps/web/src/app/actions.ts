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
  continueDataset,
  createAccount,
  createMapping,
  createSource,
  fetchDataset,
  fetchMapping,
  fetchSource,
  generateExpectations,
  linkAccount,
  setCycle,
  updateAccount,
  decideAmbiguity,
  prepareDataset,
  publishDataset,
  signIn,
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
    const source = await fetchSource(
      session.token,
      companyId,
      dataSourceId,
    );
    if (source.status !== 'active') {
      return {
        error:
          'La fuente fue retirada antes de guardar. Elige una fuente activa y revisa el mapeo.',
        mappingVersionId: null,
        blockers: [],
      };
    }
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
        error:
          'La fuente ya no esta disponible o este rol no puede mapear columnas.',
        mappingVersionId: null,
        blockers: [],
      };
    }
    if (error instanceof ApiError && error.status === 404) {
      return {
        error: 'La fuente ya no esta disponible. Elige otra fuente activa.',
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
    const mapping = await fetchMapping(session.token, companyId, mappingVersionId);
    if (mapping.artifact_id !== artifactId) {
      return {
        error:
          'El mapeo indicado ya no pertenece a este documento. Abre una version ' +
          'actual o crea el mapeo de nuevo.',
        datasetVersionId: null,
        summary: null,
        rejections: [],
      };
    }
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      redirect('/entrar');
    }
    return {
      error:
        error instanceof ApiError
          ? error.message
          : 'No se pudo validar el mapeo antes de preparar.',
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
  if (!datasetVersionId) {
    return { error: 'Falta el conjunto a publicar.', published: null };
  }

  try {
    const dataset = await fetchDataset(session.token, companyId, datasetVersionId);
    if (dataset.artifact_id !== artifactId) {
      return {
        error:
          'El conjunto indicado ya no pertenece a este documento. Elige la ' +
          'version mas reciente para publicar.',
        published: null,
      };
    }
    if (!dataset.can_publish) {
      return {
        error:
          'Ese conjunto no puede publicarse ahora; valida estado y permisos ' +
          'antes de intentar.',
        published: null,
      };
    }
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      redirect('/entrar');
    }
    return {
      error:
        error instanceof ApiError ? error.message : 'No se pudo validar el conjunto antes de publicar.',
      published: null,
    };
  }

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


// --------------------------------------------------------------------------- //
// Alta de cuentas, fuentes, vinculos y ciclos (FNC-P3.5)
// --------------------------------------------------------------------------- //

/**
 * El identificador de una cuenta viaja en el `FormData` y **no vuelve**: la API
 * lo tokeniza al recibirlo y nada de lo que devuelve lo contiene. Aqui tampoco
 * se registra ni se devuelve en un mensaje de error, porque un estado de
 * formulario acaba renderizado en el navegador.
 */

export type OnboardingState = { error: string | null; done: string | null };

function refresh(companyId: string): void {
  revalidatePath(`/empresas/${companyId}/fuentes`);
  revalidatePath(`/empresas/${companyId}`);
}

function explain(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.status === 401) {
    redirect('/entrar');
  }
  if (error instanceof ApiError && error.status === 403) {
    return 'Este rol no puede administrar cuentas ni fuentes.';
  }
  if (error instanceof ApiError) {
    return error.message;
  }
  return fallback;
}

export async function createAccountAction(
  _previous: OnboardingState,
  formData: FormData,
): Promise<OnboardingState> {
  const session = await readSession();
  if (!session) {
    redirect('/entrar');
  }
  const companyId = String(formData.get('companyId') ?? '');
  const identifier = String(formData.get('identifier') ?? '').trim();
  if (identifier.length < 4) {
    return { error: 'Escribe el identificador de la cuenta.', done: null };
  }

  let account;
  try {
    account = await createAccount(session.token, companyId, {
      account_family: String(formData.get('accountFamily') ?? 'bank_account'),
      display_name: String(formData.get('displayName') ?? '').trim(),
      identifier,
      currency_code: String(formData.get('currency') ?? 'COP').toUpperCase(),
      timezone: String(formData.get('timezone') ?? 'America/Bogota'),
    });
  } catch (error) {
    // El mensaje viene de la API, que nunca cita el identificador.
    return { error: explain(error, 'No se pudo crear la cuenta.'), done: null };
  }

  refresh(companyId);
  const tail = account.identifier_last4 ? ` terminada en ${account.identifier_last4}` : '';
  return {
    error: null,
    done: `${account.display_name}${tail} creada. El identificador no se guardo: ` +
      'lo que queda es una huella con clave.',
  };
}

export async function closeAccountAction(
  _previous: OnboardingState,
  formData: FormData,
): Promise<OnboardingState> {
  const session = await readSession();
  if (!session) {
    redirect('/entrar');
  }
  const companyId = String(formData.get('companyId') ?? '');
  const accountId = String(formData.get('accountId') ?? '');
  const status = String(formData.get('status') ?? 'suspended');
  const reason = String(formData.get('reason') ?? '').trim();
  if (status !== 'active' && reason.length < 3) {
    // Suspender o cerrar es una decision, y una decision lleva su motivo.
    return { error: 'Escribe por que se suspende o se cierra.', done: null };
  }

  try {
    await updateAccount(
      session.token,
      companyId,
      accountId,
      status === 'active' ? { status } : { status, closed_reason: reason },
    );
  } catch (error) {
    return { error: explain(error, 'No se pudo cambiar la cuenta.'), done: null };
  }
  refresh(companyId);
  return { error: null, done: `La cuenta quedo en estado ${status}.` };
}

export async function createSourceAction(
  _previous: OnboardingState,
  formData: FormData,
): Promise<OnboardingState> {
  const session = await readSession();
  if (!session) {
    redirect('/entrar');
  }
  const companyId = String(formData.get('companyId') ?? '');
  try {
    const source = await createSource(session.token, companyId, {
      source_family: String(formData.get('sourceFamily') ?? 'bank_account'),
      display_name: String(formData.get('displayName') ?? '').trim(),
      purpose_code: String(formData.get('purposeCode') ?? 'operational').trim(),
      timezone: String(formData.get('timezone') ?? 'America/Bogota'),
    });
    refresh(companyId);
    return { error: null, done: `${source.display_name} creada.` };
  } catch (error) {
    return { error: explain(error, 'No se pudo crear la fuente.'), done: null };
  }
}

export async function linkAccountAction(
  _previous: OnboardingState,
  formData: FormData,
): Promise<OnboardingState> {
  const session = await readSession();
  if (!session) {
    redirect('/entrar');
  }
  const companyId = String(formData.get('companyId') ?? '');
  const sourceId = String(formData.get('sourceId') ?? '');
  const accountId = String(formData.get('accountId') ?? '');
  if (!accountId) {
    return { error: 'Elige una cuenta.', done: null };
  }
  try {
    await linkAccount(session.token, companyId, sourceId, {
      financial_account_id: accountId,
      relation_role: String(formData.get('relationRole') ?? 'primary'),
    });
    refresh(companyId);
    return { error: null, done: 'Vinculada. Ya hay contra que publicar.' };
  } catch (error) {
    return { error: explain(error, 'No se pudo vincular.'), done: null };
  }
}

export async function setCycleAction(
  _previous: OnboardingState,
  formData: FormData,
): Promise<OnboardingState> {
  const session = await readSession();
  if (!session) {
    redirect('/entrar');
  }
  const companyId = String(formData.get('companyId') ?? '');
  const sourceId = String(formData.get('sourceId') ?? '');
  const periodicity = String(formData.get('periodicity') ?? 'monthly');
  const customDays = Number.parseInt(String(formData.get('customDays') ?? ''), 10);
  try {
    await setCycle(session.token, companyId, sourceId, {
      periodicity,
      custom_days: periodicity === 'custom' && Number.isInteger(customDays)
        ? customDays
        : null,
      due_day_offset:
        Number.parseInt(String(formData.get('dueDayOffset') ?? '5'), 10) || 0,
      grace_days: Number.parseInt(String(formData.get('graceDays') ?? '3'), 10) || 0,
      responsible_subject_id: String(formData.get('responsible') ?? ''),
      timezone: String(formData.get('timezone') ?? 'America/Bogota'),
      anchor_date: String(formData.get('anchorDate') ?? ''),
    });
    refresh(companyId);
    revalidatePath(`/empresas/${companyId}/fuentes/${sourceId}`);
    return { error: null, done: 'Ciclo guardado.' };
  } catch (error) {
    return { error: explain(error, 'No se pudo guardar el ciclo.'), done: null };
  }
}

export async function generateExpectationsAction(
  _previous: OnboardingState,
  formData: FormData,
): Promise<OnboardingState> {
  const session = await readSession();
  if (!session) {
    redirect('/entrar');
  }
  const companyId = String(formData.get('companyId') ?? '');
  const sourceId = String(formData.get('sourceId') ?? '');
  const until = String(formData.get('until') ?? '');
  if (!until) {
    return { error: 'Elige hasta que fecha calcular los periodos.', done: null };
  }
  try {
    const report = await generateExpectations(
      session.token,
      companyId,
      sourceId,
      until,
    );
    refresh(companyId);
    revalidatePath(`/empresas/${companyId}/fuentes/${sourceId}`);
    return {
      error: null,
      done: `${report.periods} periodo(s) calculados; ${report.created} nuevo(s).`,
    };
  } catch (error) {
    return {
      error: explain(error, 'El ciclo se conserva, pero no se pudieron calcular los periodos.'),
      done: null,
    };
  }
}

export type ContinueState = { error: string | null; progress: string | null };

export async function continueDatasetAction(
  _previous: ContinueState,
  formData: FormData,
): Promise<ContinueState> {
  const session = await readSession();
  if (!session) {
    redirect('/entrar');
  }
  const companyId = String(formData.get('companyId') ?? '');
  const artifactId = String(formData.get('artifactId') ?? '');
  const datasetId = String(formData.get('datasetVersionId') ?? '');
  if (!datasetId) {
    return { error: 'Falta el conjunto a continuar.', progress: null };
  }
  try {
    const dataset = await fetchDataset(session.token, companyId, datasetId);
    if (dataset.artifact_id !== artifactId) {
      return {
        error:
          'La version a continuar ya no pertenece a este documento. ' +
          'Abre la version actual de este documento.',
        progress: null,
      };
    }
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      redirect('/entrar');
    }
    return { error: error instanceof ApiError ? error.message : 'No se pudo validar el conjunto antes de continuar.', progress: null };
  }

  try {
    const report = await continueDataset(session.token, companyId, datasetId);
    revalidatePath(`/empresas/${companyId}/documentos/${artifactId}/mapeo`);
    return {
      error: null,
      progress: report.complete
        ? `Terminado: ${report.movement_count} movimiento(s) listos para revisar.`
        : `Va por ${report.movement_count} movimiento(s). Sigue pulsando: cada ` +
          'tanda entra con su punto de control y no se repite.',
    };
  } catch (error) {
    return { error: explain(error, 'No se pudo continuar.'), progress: null };
  }
}

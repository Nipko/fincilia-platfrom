'use server';

/**
 * Acciones de servidor. El formulario no llama a la API: llama aqui, y este
 * proceso llama a la API. Asi el token nunca cruza al navegador.
 */

import { revalidatePath } from 'next/cache';
import { redirect } from 'next/navigation';

import {
  ApiError,
  applyApprovedCorrections,
  approveOverride,
  type Blocker,
  continueDataset,
  fetchCorrectionTargets,
  fetchCorrections,
  createAccount,
  createAccountBalance,
  createBalanceReconciliationStatement,
  createCompletenessAssessment,
  createMapping,
  createReconcilingItem,
  createSource,
  fetchDataset,
  fetchMapping,
  fetchOverrides,
  fetchSource,
  grantMemberRole,
  generateExpectations,
  linkAccount,
  setCycle,
  updateAccount,
  decideAmbiguity,
  decideReconcilingItem,
  prepareDataset,
  publishDataset,
  provisionCompany,
  proposeReconciliationGroup,
  proposeReconciliationReview,
  proposeCorrection,
  rejectDataset,
  decideReconciliationReview,
  reviewCorrection,
  revokeMemberRole,
  scanQualityIssues,
  signIn,
  triageQualityIssue,
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
// Observaciones canonicas de saldo (FNC-CLS-002)
// --------------------------------------------------------------------------- //

export type BalanceObservationState = { error: string | null; done: string | null };

const BALANCE_TYPES = new Set(['opening', 'closing', 'running', 'available', 'ledger']);

export async function observeBalanceAction(
  _previous: BalanceObservationState,
  formData: FormData,
): Promise<BalanceObservationState> {
  const session = await readSession();
  if (!session) redirect('/entrar');
  const companyId = String(formData.get('companyId') ?? '');
  const sourceRecordId = String(formData.get('sourceRecordId') ?? '');
  const balanceType = String(formData.get('balanceType') ?? '');
  const amountFieldIndex = Number.parseInt(
    String(formData.get('amountFieldIndex') ?? ''), 10);
  const asOfFieldIndex = Number.parseInt(
    String(formData.get('asOfFieldIndex') ?? ''), 10);
  if (
    !UUID_PATTERN.test(companyId) || !UUID_PATTERN.test(sourceRecordId) ||
    !BALANCE_TYPES.has(balanceType) ||
    !Number.isInteger(amountFieldIndex) || amountFieldIndex < 0 || amountFieldIndex > 2047 ||
    !Number.isInteger(asOfFieldIndex) || asOfFieldIndex < 0 || asOfFieldIndex > 2047
  ) {
    return { error: 'Selecciona una fila, un tipo y dos columnas validas.', done: null };
  }
  try {
    const result = await createAccountBalance(session.token, companyId, {
      source_record_id: sourceRecordId,
      balance_type: balanceType as 'opening' | 'closing' | 'running' | 'available' | 'ledger',
      amount_field_index: amountFieldIndex,
      as_of_field_index: asOfFieldIndex,
    });
    revalidatePath(`/empresas/${companyId}/saldos`);
    revalidatePath('/preparacion-cierre');
    return {
      error: null,
      done: result.replayed
        ? 'La misma observacion ya estaba registrada; no se duplico.'
        : 'Saldo observado. Sigue pendiente completar el linaje antes de usarlo en cierre.',
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    if (error instanceof ApiError && error.status === 403) {
      return { error: 'La evidencia ya no esta publicada o tu acceso cambio.', done: null };
    }
    if (error instanceof ApiError && error.status === 409) {
      return { error: 'Esa coordenada ya tiene otra observacion. Revisa el historico.', done: null };
    }
    if (error instanceof ApiError && error.status === 422) {
      return { error: 'Las celdas no se pueden leer con el mapeo versionado.', done: null };
    }
    return { error: 'No se pudo registrar el saldo. Intenta de nuevo.', done: null };
  }
}

// --------------------------------------------------------------------------- //
// Estados diagnosticos de conciliacion de saldos (FNC-CLS-003)
// --------------------------------------------------------------------------- //

export type BalanceReconciliationActionState = {
  error: string | null;
  done: string | null;
};

function reconciliationPath(companyId: string): string {
  return `/empresas/${companyId}/conciliacion-saldos`;
}

function reconciliationApiError(error: unknown): BalanceReconciliationActionState {
  if (error instanceof ApiError && error.status === 403) {
    return { error: 'La evidencia no esta disponible, tu acceso cambio o falta otro revisor.', done: null };
  }
  if (error instanceof ApiError && error.status === 409) {
    return { error: 'El estado cambio o la misma persona intento preparar y aprobar.', done: null };
  }
  if (error instanceof ApiError && error.status === 422) {
    return { error: 'Las fuentes no comparten cuenta, moneda, periodo o version.', done: null };
  }
  return { error: 'No se pudo aplicar la operacion. Intenta de nuevo.', done: null };
}

export async function assessCompletenessAction(
  _previous: BalanceReconciliationActionState,
  formData: FormData,
): Promise<BalanceReconciliationActionState> {
  const session = await readSession();
  if (!session) redirect('/entrar');
  const companyId = String(formData.get('companyId') ?? '');
  const expectationId = String(formData.get('expectationId') ?? '');
  if (!UUID_PATTERN.test(companyId) || !UUID_PATTERN.test(expectationId)) {
    return { error: 'La expectativa seleccionada no es valida.', done: null };
  }
  try {
    const result = await createCompletenessAssessment(
      session.token, companyId, expectationId);
    revalidatePath(reconciliationPath(companyId));
    return {
      error: null,
      done: result.replayed
        ? 'La misma evaluacion ya existia; no se duplico.'
        : result.state === 'verified'
          ? 'Completitud evaluada con controles verificables.'
          : 'Evaluacion registrada. Los controles desconocidos siguen bloqueando.',
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    return reconciliationApiError(error);
  }
}

export async function evaluateBalanceReconciliationAction(
  _previous: BalanceReconciliationActionState,
  formData: FormData,
): Promise<BalanceReconciliationActionState> {
  const session = await readSession();
  if (!session) redirect('/entrar');
  const companyId = String(formData.get('companyId') ?? '');
  const bankBalanceId = String(formData.get('bankBalanceId') ?? '');
  const booksBalanceId = String(formData.get('booksBalanceId') ?? '');
  const assessmentIds = formData.getAll('assessmentIds').map(String);
  if (
    !UUID_PATTERN.test(companyId) || !UUID_PATTERN.test(bankBalanceId) ||
    !UUID_PATTERN.test(booksBalanceId) || assessmentIds.length === 0 ||
    assessmentIds.length > 1000 || assessmentIds.some((value) => !UUID_PATTERN.test(value)) ||
    new Set(assessmentIds).size !== assessmentIds.length
  ) {
    return { error: 'Selecciona dos saldos y al menos una evaluacion valida.', done: null };
  }
  try {
    const result = await createBalanceReconciliationStatement(
      session.token, companyId, {
        bank_balance_id: bankBalanceId,
        books_balance_id: booksBalanceId,
        assessment_ids: assessmentIds,
      });
    revalidatePath(reconciliationPath(companyId));
    revalidatePath('/preparacion-cierre');
    return {
      error: null,
      done: result.replayed
        ? `La version ${result.version} ya existia; no se duplico.`
        : `Version ${result.version} calculada: ${result.state === 'balanced' ? 'diferencia explicada' : 'requiere revision'}.`,
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    return reconciliationApiError(error);
  }
}

const ITEM_SIDES = new Set(['add_to_bank', 'deduct_from_bank']);
const ITEM_REASONS = new Set([
  'bank_fee_pending', 'deposit_in_transit', 'documented_timing',
  'outstanding_payment', 'other_documented',
]);
const EXACT_POSITIVE_MONEY = /^(?=.*[1-9])\d{1,26}(?:\.\d{1,12})?$/;

export async function proposeReconcilingItemAction(
  _previous: BalanceReconciliationActionState,
  formData: FormData,
): Promise<BalanceReconciliationActionState> {
  const session = await readSession();
  if (!session) redirect('/entrar');
  const companyId = String(formData.get('companyId') ?? '');
  const statementRootId = String(formData.get('statementRootId') ?? '');
  const amount = String(formData.get('amount') ?? '').trim();
  const adjustmentSide = String(formData.get('adjustmentSide') ?? '');
  const reasonCode = String(formData.get('reasonCode') ?? '');
  const evidenceIds = formData.getAll('evidenceSourceRecordIds').map(String);
  if (
    !UUID_PATTERN.test(companyId) || !UUID_PATTERN.test(statementRootId) ||
    !EXACT_POSITIVE_MONEY.test(amount) || !ITEM_SIDES.has(adjustmentSide) ||
    !ITEM_REASONS.has(reasonCode) || evidenceIds.length === 0 ||
    evidenceIds.length > 50 || evidenceIds.some((value) => !UUID_PATTERN.test(value)) ||
    new Set(evidenceIds).size !== evidenceIds.length
  ) {
    return { error: 'Completa monto, lado, motivo y evidencia valida.', done: null };
  }
  try {
    await createReconcilingItem(
      session.token, companyId, statementRootId, {
        amount,
        adjustment_side: adjustmentSide as 'add_to_bank' | 'deduct_from_bank',
        reason_code: reasonCode,
        evidence_source_record_ids: evidenceIds,
      });
    revalidatePath(reconciliationPath(companyId));
    return { error: null, done: 'Partida propuesta. Aun no entra en la ecuacion.' };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    return reconciliationApiError(error);
  }
}

export async function decideReconcilingItemAction(
  _previous: BalanceReconciliationActionState,
  formData: FormData,
): Promise<BalanceReconciliationActionState> {
  const session = await readSession();
  if (!session) redirect('/entrar');
  const companyId = String(formData.get('companyId') ?? '');
  const itemRootId = String(formData.get('itemRootId') ?? '');
  const decision = String(formData.get('decision') ?? '');
  if (
    !UUID_PATTERN.test(companyId) || !UUID_PATTERN.test(itemRootId) ||
    !['confirmed', 'rejected', 'reversed'].includes(decision)
  ) {
    return { error: 'La decision seleccionada no es valida.', done: null };
  }
  try {
    const result = await decideReconcilingItem(
      session.token, companyId, itemRootId,
      decision as 'confirmed' | 'rejected' | 'reversed');
    revalidatePath(reconciliationPath(companyId));
    return {
      error: null,
      done: result.replayed
        ? 'La misma decision ya estaba registrada.'
        : 'Decision append-only registrada. Recalcula el estado para incorporarla.',
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    return reconciliationApiError(error);
  }
}

// --------------------------------------------------------------------------- //
// Alta transaccional de empresa (FNC-ONB-001)
// --------------------------------------------------------------------------- //

export type CompanyProvisionState = { error: string | null };

const COUNTRY_CODES = new Set(['AR', 'CL', 'CO', 'MX', 'PE']);
const ACCOUNT_FAMILIES = new Set([
  'bank_account', 'payment_gateway', 'merchant_acquirer', 'marketplace',
  'digital_wallet', 'billing_erp', 'accounting_ledger',
]);
const SOURCE_FAMILIES = new Set([
  'bank_account', 'payment_gateway', 'merchant_acquirer', 'marketplace',
  'digital_wallet', 'billing_erp', 'accounting_ledger',
  'tax_documents_received', 'supporting_evidence', 'reference_data',
]);
const COMPANY_IDEMPOTENCY_PATTERN = /^[A-Za-z0-9._:-]{16,128}$/;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export async function provisionCompanyAction(
  _previous: CompanyProvisionState,
  formData: FormData,
): Promise<CompanyProvisionState> {
  const session = await readSession();
  if (!session) redirect('/entrar');

  const firmId = String(formData.get('firmId') ?? '');
  const legalName = String(formData.get('legalName') ?? '').trim();
  const countryCode = String(formData.get('countryCode') ?? '').toUpperCase();
  const taxIdentifier = String(formData.get('taxIdentifier') ?? '').trim();
  const idempotencyKey = String(formData.get('idempotencyKey') ?? '');
  const includeSetup = formData.get('includeSetup') === 'on';
  if (
    !UUID_PATTERN.test(firmId) || legalName.length < 2 || legalName.length > 300 ||
    !COUNTRY_CODES.has(countryCode) || taxIdentifier.length < 4 ||
    taxIdentifier.length > 64 || !COMPANY_IDEMPOTENCY_PATTERN.test(idempotencyKey)
  ) {
    return { error: 'Revisa la firma, nombre, pais e identificacion protegida.' };
  }

  let setup = null;
  if (includeSetup) {
    const accountFamily = String(formData.get('accountFamily') ?? '');
    const sourceFamily = String(formData.get('sourceFamily') ?? '');
    const accountName = String(formData.get('accountName') ?? '').trim();
    const accountIdentifier = String(formData.get('accountIdentifier') ?? '').trim();
    const sourceName = String(formData.get('sourceName') ?? '').trim();
    const currencyCode = String(formData.get('currencyCode') ?? '').toUpperCase();
    const timezone = String(formData.get('timezone') ?? 'America/Bogota');
    const anchorDate = String(formData.get('anchorDate') ?? '');
    const dueDayOffset = Number.parseInt(
      String(formData.get('dueDayOffset') ?? '0'), 10);
    const graceDays = Number.parseInt(String(formData.get('graceDays') ?? '3'), 10);
    if (
      !ACCOUNT_FAMILIES.has(accountFamily) || !SOURCE_FAMILIES.has(sourceFamily) ||
      accountName.length < 1 || accountName.length > 160 ||
      accountIdentifier.length < 4 || accountIdentifier.length > 64 ||
      sourceName.length < 1 || sourceName.length > 160 ||
      !/^[A-Z]{3}$/.test(currencyCode) || !/^\d{4}-\d{2}-\d{2}$/.test(anchorDate) ||
      !Number.isInteger(dueDayOffset) || dueDayOffset < 0 || dueDayOffset > 120 ||
      !Number.isInteger(graceDays) || graceDays < 0 || graceDays > 120
    ) {
      return { error: 'Revisa la cuenta, fuente y ciclo inicial.' };
    }
    setup = {
      account_family: accountFamily,
      account_name: accountName,
      account_identifier: accountIdentifier,
      currency_code: currencyCode,
      source_family: sourceFamily,
      source_name: sourceName,
      purpose_code: 'operational',
      timezone,
      anchor_date: anchorDate,
      due_day_offset: dueDayOffset,
      grace_days: graceDays,
    };
  }

  let result;
  try {
    result = await provisionCompany(session.token, {
      firm_id: firmId,
      legal_name: legalName,
      country_code: countryCode,
      tax_identifier: taxIdentifier,
      setup,
    }, idempotencyKey);
    await writeSession(
      result.refreshed_session.token,
      result.refreshed_session.display_name,
      result.refreshed_session.expires_at,
    );
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    if (error instanceof ApiError && error.status === 403) {
      return { error: 'Ya no puedes crear empresas para esa firma.' };
    }
    if (error instanceof ApiError && error.status === 409) {
      return { error: 'La empresa ya esta registrada o la solicitud cambio al reintentarse.' };
    }
    if (error instanceof ApiError && error.status === 422) {
      return { error: 'La empresa o su configuracion inicial no son validas.' };
    }
    return { error: 'No se pudo crear la empresa. Intenta nuevamente.' };
  }

  revalidatePath('/empresas');
  redirect(`/empresas/${result.company_id}/fuentes?alta=creada`);
}

// --------------------------------------------------------------------------- //
// Administracion de equipo y roles (FNC-QA-007)
// --------------------------------------------------------------------------- //

export type RoleManagementState = { error: string | null; done: string | null };

const COMPANY_ROLES = new Set([
  'owner',
  'firm_admin',
  'preparer',
  'reviewer',
  'auditor',
  'read_only',
]);
const ROLE_REASON_CODES = new Set([
  'access_required',
  'responsibility_change',
  'team_change',
  'least_privilege',
  'access_removed',
]);

function roleManagementError(error: unknown): RoleManagementState {
  if (error instanceof ApiError && error.status === 403) {
    return {
      error: 'Tu rol no puede administrar este acceso o el miembro ya no esta disponible.',
      done: null,
    };
  }
  if (error instanceof ApiError && error.status === 409) {
    return {
      error: 'El cambio entra en conflicto con la proteccion del ultimo owner o con una accion propia.',
      done: null,
    };
  }
  if (error instanceof ApiError && error.status === 422) {
    return { error: 'El miembro, el rol o el motivo ya no son validos.', done: null };
  }
  if (error instanceof ApiError && error.status === 503) {
    return { error: 'La administracion de accesos no esta disponible.', done: null };
  }
  return {
    error: error instanceof ApiError ? error.message : 'No se pudo cambiar el rol.',
    done: null,
  };
}

async function changeMemberRoleAction(
  operation: 'grant' | 'revoke',
  formData: FormData,
): Promise<RoleManagementState> {
  const session = await readSession();
  if (!session) redirect('/entrar');
  const companyId = String(formData.get('companyId') ?? '');
  const subjectId = String(formData.get('subjectId') ?? '');
  const role = String(formData.get('role') ?? '');
  const reasonCode = String(formData.get('reasonCode') ?? '');
  if (
    !UUID_PATTERN.test(companyId) || !UUID_PATTERN.test(subjectId) ||
    !COMPANY_ROLES.has(role) || !ROLE_REASON_CODES.has(reasonCode)
  ) {
    return { error: 'El cambio de acceso no tiene un contexto valido.', done: null };
  }
  try {
    const result = operation === 'grant'
      ? await grantMemberRole(session.token, companyId, subjectId, {
          role,
          reason_code: reasonCode,
        })
      : await revokeMemberRole(session.token, companyId, subjectId, {
          role,
          reason_code: reasonCode,
        });
    if (result.refreshed_session) {
      await writeSession(
        result.refreshed_session.token,
        result.refreshed_session.display_name,
        result.refreshed_session.expires_at,
      );
    }
    revalidatePath(`/empresas/${companyId}/equipo`);
    revalidatePath(`/empresas/${companyId}`);
    if (operation === 'grant') {
      return {
        error: null,
        done: result.replayed
          ? 'El miembro ya tenia ese rol.'
          : 'Rol asignado y sesiones anteriores invalidadas.',
      };
    }
    return {
      error: null,
      done: result.replayed
        ? 'El rol ya estaba revocado.'
        : 'Rol revocado y sesiones anteriores invalidadas.',
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    return roleManagementError(error);
  }
}

export async function grantMemberRoleAction(
  _previous: RoleManagementState,
  formData: FormData,
): Promise<RoleManagementState> {
  return changeMemberRoleAction('grant', formData);
}

export async function revokeMemberRoleAction(
  _previous: RoleManagementState,
  formData: FormData,
): Promise<RoleManagementState> {
  return changeMemberRoleAction('revoke', formData);
}

// --------------------------------------------------------------------------- //
// Revision humana de candidatos de conciliacion (FNC-REC-002)
// --------------------------------------------------------------------------- //

export type MatchReviewState = { error: string | null; done: string | null };

const IDEMPOTENCY_PATTERN = /^[A-Za-z0-9._:-]{16,128}$/;

function reviewError(error: unknown): MatchReviewState {
  if (error instanceof ApiError && error.status === 403) {
    return { error: 'El candidato o el permiso ya no estan disponibles.', done: null };
  }
  if (error instanceof ApiError && error.status === 409) {
    if (error.code === 'movement-already-confirmed') {
      return {
        error: 'Uno de los movimientos ya fue confirmado con otra contraparte. Revisa ambos expedientes; no se registro esta decision.',
        done: null,
      };
    }
    return {
      error: 'El comando entra en conflicto con una decision, una clave previa o la segregacion de funciones.',
      done: null,
    };
  }
  if (error instanceof ApiError && error.status === 422) {
    return { error: 'La propuesta ya no cumple el contrato de revision.', done: null };
  }
  if (error instanceof ApiError && error.status === 503) {
    return { error: 'La revision no esta habilitada en este entorno.', done: null };
  }
  return {
    error: error instanceof ApiError ? error.message : 'No se pudo registrar la revision.',
    done: null,
  };
}

export async function proposeMatchAction(
  _previous: MatchReviewState,
  formData: FormData,
): Promise<MatchReviewState> {
  const session = await readSession();
  if (!session) redirect('/entrar');
  const companyId = String(formData.get('companyId') ?? '');
  const leftDatasetId = String(formData.get('leftDatasetId') ?? '');
  const rightDatasetId = String(formData.get('rightDatasetId') ?? '');
  const leftMovementId = String(formData.get('leftMovementId') ?? '');
  const rightMovementId = String(formData.get('rightMovementId') ?? '');
  const idempotencyKey = String(formData.get('idempotencyKey') ?? '');
  const maxDays = Number.parseInt(String(formData.get('maxDays') ?? ''), 10);
  if (
    ![companyId, leftDatasetId, rightDatasetId, leftMovementId, rightMovementId]
      .every((value) => UUID_PATTERN.test(value)) ||
    !IDEMPOTENCY_PATTERN.test(idempotencyKey) ||
    !Number.isInteger(maxDays) || maxDays < 0 || maxDays > 31
  ) {
    return { error: 'El candidato visible ya no tiene un contexto valido.', done: null };
  }
  try {
    const result = await proposeReconciliationReview(
      session.token,
      companyId,
      idempotencyKey,
      {
        left_dataset_id: leftDatasetId,
        right_dataset_id: rightDatasetId,
        left_movement_id: leftMovementId,
        right_movement_id: rightMovementId,
        max_days: maxDays,
      },
    );
    revalidatePath(`/empresas/${companyId}/conciliacion`);
    return {
      error: null,
      done: result.replayed
        ? 'La misma propuesta ya estaba registrada.'
        : result.created
          ? 'Propuesta registrada. No cambia movimientos ni saldos.'
          : 'El par ya estaba propuesto; se vinculó el comando sin duplicarlo.',
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    return reviewError(error);
  }
}

export async function decideMatchAction(
  _previous: MatchReviewState,
  formData: FormData,
): Promise<MatchReviewState> {
  const session = await readSession();
  if (!session) redirect('/entrar');
  const companyId = String(formData.get('companyId') ?? '');
  const candidateId = String(formData.get('candidateId') ?? '');
  const idempotencyKey = String(formData.get('idempotencyKey') ?? '');
  const decision = String(formData.get('decision') ?? '');
  const reasonCode = String(formData.get('reasonCode') ?? '');
  if (
    !UUID_PATTERN.test(companyId) || !UUID_PATTERN.test(candidateId) ||
    !IDEMPOTENCY_PATTERN.test(idempotencyKey) ||
    !['confirmed', 'rejected'].includes(decision) || !reasonCode
  ) {
    return { error: 'La decision visible ya no tiene un contexto valido.', done: null };
  }
  try {
    const result = await decideReconciliationReview(
      session.token,
      companyId,
      candidateId,
      idempotencyKey,
      decision as 'confirmed' | 'rejected',
      reasonCode,
    );
    revalidatePath(`/empresas/${companyId}/conciliacion`);
    return {
      error: null,
      done: result.replayed
        ? 'La misma decision ya estaba registrada.'
        : decision === 'confirmed'
          ? 'Revision confirmada. Sigue sin efecto sobre movimientos o saldos.'
          : 'Candidato rechazado; la evidencia y el movimiento base se conservan.',
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    return reviewError(error);
  }
}

export async function proposeMatchGroupAction(
  _previous: MatchReviewState,
  formData: FormData,
): Promise<MatchReviewState> {
  const session = await readSession();
  if (!session) redirect('/entrar');
  const companyId = String(formData.get('companyId') ?? '');
  const anchorDatasetId = String(formData.get('anchorDatasetId') ?? '');
  const relatedDatasetId = String(formData.get('relatedDatasetId') ?? '');
  const anchorMovementId = String(formData.get('anchorMovementId') ?? '');
  const relatedMovementIds = formData.getAll('relatedMovementIds').map(String);
  const idempotencyKey = String(formData.get('idempotencyKey') ?? '');
  if (
    ![companyId, anchorDatasetId, relatedDatasetId, anchorMovementId]
      .every((value) => UUID_PATTERN.test(value)) ||
    anchorDatasetId === relatedDatasetId ||
    !IDEMPOTENCY_PATTERN.test(idempotencyKey) ||
    relatedMovementIds.length < 2 || relatedMovementIds.length > 49 ||
    relatedMovementIds.some((value) => !UUID_PATTERN.test(value)) ||
    new Set(relatedMovementIds).size !== relatedMovementIds.length ||
    relatedMovementIds.includes(anchorMovementId)
  ) {
    return {
      error: 'El grupo visible ya no tiene una composicion valida de 2 a 49 movimientos.',
      done: null,
    };
  }
  try {
    const result = await proposeReconciliationGroup(
      session.token,
      companyId,
      idempotencyKey,
      {
        anchor_dataset_id: anchorDatasetId,
        related_dataset_id: relatedDatasetId,
        anchor_movement_id: anchorMovementId,
        related_movement_ids: relatedMovementIds,
      },
    );
    revalidatePath(`/empresas/${companyId}/conciliacion`);
    return {
      error: null,
      done: result.replayed
        ? 'El mismo borrador agrupado ya estaba registrado.'
        : result.created
          ? 'Borrador agrupado registrado, sin asignaciones ni efecto financiero.'
          : 'La composicion ya existia; el comando se vinculo sin duplicarla.',
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    if (error instanceof ApiError && error.status === 403) {
      return { error: 'Los movimientos o el permiso ya no estan disponibles.', done: null };
    }
    if (error instanceof ApiError && error.status === 409) {
      return { error: 'La clave ya fue usada para otra composicion.', done: null };
    }
    if (error instanceof ApiError && error.status === 422) {
      return {
        error: 'El servidor rechazo el grupo: revisa datasets, moneda, direccion y miembros.',
        done: null,
      };
    }
    if (error instanceof ApiError && error.status === 503) {
      return { error: 'Los borradores agrupados no estan habilitados aqui.', done: null };
    }
    return {
      error: error instanceof ApiError ? error.message : 'No se pudo registrar el grupo.',
      done: null,
    };
  }
}

// --------------------------------------------------------------------------- //
// Triaje de alertas deterministas de calidad (FNC-DQ-001)
// --------------------------------------------------------------------------- //

export type QualityActionState = { error: string | null; done: string | null };

function qualityActionError(error: unknown): QualityActionState {
  if (error instanceof ApiError && error.status === 403) {
    return { error: 'La alerta o el permiso ya no estan disponibles.', done: null };
  }
  if (error instanceof ApiError && error.status === 409) {
    return { error: 'La alerta ya tiene un estado terminal.', done: null };
  }
  if (error instanceof ApiError && error.status === 422) {
    return { error: 'El estado, motivo o comentario no cumplen el contrato.', done: null };
  }
  if (error instanceof ApiError && error.status === 503) {
    return { error: 'El centro de calidad no esta disponible.', done: null };
  }
  return {
    error: error instanceof ApiError ? error.message : 'No se pudo completar la accion.',
    done: null,
  };
}

export async function scanQualityAction(
  _previous: QualityActionState,
  formData: FormData,
): Promise<QualityActionState> {
  const session = await readSession();
  if (!session) redirect('/entrar');
  const companyId = String(formData.get('companyId') ?? '');
  if (!UUID_PATTERN.test(companyId)) {
    return { error: 'La empresa ya no tiene un contexto valido.', done: null };
  }
  try {
    const result = await scanQualityIssues(session.token, companyId);
    revalidatePath('/calidad');
    revalidatePath(`/empresas/${companyId}`);
    return {
      error: null,
      done: result.truncated
        ? `Se evaluo la ventana segura y se detectaron ${result.findings} senales; algunas reglas alcanzaron su limite.`
        : `Evaluacion completa de la ventana: ${result.findings} senales, ${result.created} nuevas.`,
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    return qualityActionError(error);
  }
}

const QUALITY_REASONS: Record<string, Set<string>> = {
  acknowledged: new Set(['investigate']),
  resolved: new Set(['reviewed_source', 'corrected_upstream', 'duplicate_confirmed']),
  dismissed: new Set(['expected_pattern', 'false_positive', 'not_applicable']),
};

export async function triageQualityAction(
  _previous: QualityActionState,
  formData: FormData,
): Promise<QualityActionState> {
  const session = await readSession();
  if (!session) redirect('/entrar');
  const companyId = String(formData.get('companyId') ?? '');
  const issueId = String(formData.get('issueId') ?? '');
  const status = String(formData.get('status') ?? '');
  const reasonCode = String(formData.get('reasonCode') ?? '');
  const rationale = String(formData.get('rationale') ?? '').trim();
  if (
    !UUID_PATTERN.test(companyId) || !UUID_PATTERN.test(issueId)
    || !QUALITY_REASONS[status]?.has(reasonCode)
    || rationale.length < 10 || rationale.length > 500
  ) {
    return { error: 'La accion de calidad no tiene un contexto valido.', done: null };
  }
  try {
    const result = await triageQualityIssue(
      session.token, companyId, issueId,
      { status, reason_code: reasonCode, rationale },
    );
    revalidatePath('/calidad');
    return {
      error: null,
      done: result.replayed
        ? 'La misma revision ya estaba registrada.'
        : status === 'acknowledged'
          ? 'Caso tomado para investigacion; no cambia ningun dato financiero.'
          : status === 'resolved'
            ? 'Caso resuelto con motivo y auditoria.'
            : 'Senal descartada con motivo y auditoria.',
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    return qualityActionError(error);
  }
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

export type ReviewState = { error: string | null; done: string | null };

/** Aprueba una excepcion solo despues de volver a ligarla al dataset visible. */
export async function approveOverrideAction(
  _previous: ReviewState,
  formData: FormData,
): Promise<ReviewState> {
  const session = await readSession();
  if (!session) {
    redirect('/entrar');
  }
  const companyId = String(formData.get('companyId') ?? '');
  const artifactId = String(formData.get('artifactId') ?? '');
  const datasetVersionId = String(formData.get('datasetVersionId') ?? '');
  const overrideId = String(formData.get('overrideId') ?? '');
  if (!datasetVersionId || !overrideId) {
    return { error: 'Falta identificar la excepcion a revisar.', done: null };
  }

  try {
    const dataset = await fetchDataset(session.token, companyId, datasetVersionId);
    if (dataset.artifact_id !== artifactId) {
      return {
        error: 'El conjunto ya no pertenece al documento que estas revisando.',
        done: null,
      };
    }
    const overrides = await fetchOverrides(
      session.token,
      companyId,
      datasetVersionId,
    );
    if (!overrides.some((item) => item.override_id === overrideId)) {
      return {
        error: 'La excepcion ya no pertenece a este conjunto o fue sustituida.',
        done: null,
      };
    }
    await approveOverride(session.token, companyId, overrideId);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      redirect('/entrar');
    }
    if (error instanceof ApiError && error.status === 403) {
      return { error: 'Este rol no puede aprobar excepciones.', done: null };
    }
    if (error instanceof ApiError && error.status === 409) {
      return {
        error: 'Quien registro la excepcion no puede aprobarla.',
        done: null,
      };
    }
    if (error instanceof ApiError && error.status === 422) {
      return {
        error: 'La excepcion ya no es aprobable en el estado actual.',
        done: null,
      };
    }
    return {
      error:
        error instanceof ApiError
          ? error.message
          : 'No se pudo aprobar la excepcion.',
      done: null,
    };
  }

  revalidatePath(`/empresas/${companyId}/documentos/${artifactId}/mapeo`);
  return { error: null, done: 'Excepcion aprobada por una persona distinta.' };
}

export type CorrectionState = { error: string | null; done: string | null };
export type CorrectionApplicationState = {
  error: string | null;
  done: string | null;
  resultDatasetVersionId: string | null;
};

/** Propone; vuelve a ligar todos los IDs y el digest a la lectura autorizada. */
export async function proposeCorrectionAction(
  _previous: CorrectionState,
  formData: FormData,
): Promise<CorrectionState> {
  const session = await readSession();
  if (!session) {
    redirect('/entrar');
  }
  const companyId = String(formData.get('companyId') ?? '');
  const artifactId = String(formData.get('artifactId') ?? '');
  const datasetVersionId = String(formData.get('datasetVersionId') ?? '');
  const movementId = String(formData.get('movementId') ?? '');
  const field = String(formData.get('field') ?? '');
  const expectedBaseDigest = String(formData.get('expectedBaseDigest') ?? '');
  const newValue = String(formData.get('newValue') ?? '').trim();
  const reasonCode = String(formData.get('reasonCode') ?? '');
  const reasonComment = String(formData.get('reasonComment') ?? '').trim();
  if (!datasetVersionId || !movementId || !field || !newValue || !reasonComment) {
    return { error: 'Completa campo, valor y motivo de la correccion.', done: null };
  }
  if (reasonComment.length > 500) {
    return { error: 'El motivo no puede superar 500 caracteres.', done: null };
  }

  try {
    const [dataset, targets] = await Promise.all([
      fetchDataset(session.token, companyId, datasetVersionId),
      fetchCorrectionTargets(session.token, companyId, datasetVersionId, movementId),
    ]);
    if (dataset.artifact_id !== artifactId || dataset.state !== 'validated') {
      return {
        error: 'El conjunto ya no es la version validada que estabas corrigiendo.',
        done: null,
      };
    }
    const target = targets.find((item) => item.field === field);
    if (!target || target.expected_base_digest !== expectedBaseDigest) {
      return {
        error: 'El campo cambio desde que abriste la pantalla; vuelve a cargar.',
        done: null,
      };
    }
    await proposeCorrection(session.token, companyId, datasetVersionId, {
      movement_id: movementId,
      field,
      expected_base_digest: expectedBaseDigest,
      new_value: newValue,
      reason_code: reasonCode,
      reason_comment: reasonComment,
    });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      redirect('/entrar');
    }
    if (error instanceof ApiError && error.status === 403) {
      return { error: 'Este rol no puede proponer correcciones.', done: null };
    }
    if (error instanceof ApiError && error.status === 409) {
      return {
        error: 'La base cambio o ya existe una correccion activa para ese campo.',
        done: null,
      };
    }
    return {
      error: error instanceof ApiError ? error.message : 'No se pudo proponer la correccion.',
      done: null,
    };
  }

  revalidatePath(`/empresas/${companyId}/movimientos/${movementId}`);
  revalidatePath(`/empresas/${companyId}/documentos/${artifactId}/mapeo`);
  return {
    error: null,
    done: 'Correccion propuesta. Todavia no cambia el movimiento: requiere revision.',
  };
}

/** Revisa; aprobar autoriza el siguiente reproceso, pero no aplica el valor. */
export async function reviewCorrectionAction(
  _previous: CorrectionState,
  formData: FormData,
): Promise<CorrectionState> {
  const session = await readSession();
  if (!session) {
    redirect('/entrar');
  }
  const companyId = String(formData.get('companyId') ?? '');
  const artifactId = String(formData.get('artifactId') ?? '');
  const datasetVersionId = String(formData.get('datasetVersionId') ?? '');
  const overlayId = String(formData.get('overlayId') ?? '');
  const decision = String(formData.get('decision') ?? '');
  const rationale = String(formData.get('rationale') ?? '').trim();
  if (!overlayId || !rationale || !['approved', 'rejected'].includes(decision)) {
    return { error: 'Elige una decision y explica el motivo.', done: null };
  }
  if (rationale.length > 500) {
    return { error: 'La justificacion no puede superar 500 caracteres.', done: null };
  }

  try {
    const [dataset, corrections] = await Promise.all([
      fetchDataset(session.token, companyId, datasetVersionId),
      fetchCorrections(session.token, companyId, datasetVersionId),
    ]);
    if (dataset.artifact_id !== artifactId) {
      return { error: 'El conjunto ya no pertenece al documento visible.', done: null };
    }
    const correction = corrections.find((item) => item.overlay_id === overlayId);
    if (!correction || correction.status !== 'pending_review') {
      return { error: 'La correccion ya no esta pendiente en este conjunto.', done: null };
    }
    await reviewCorrection(
      session.token, companyId, overlayId,
      decision as 'approved' | 'rejected', rationale,
    );
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      redirect('/entrar');
    }
    if (error instanceof ApiError && error.status === 403) {
      return { error: 'Este rol no puede revisar correcciones.', done: null };
    }
    if (error instanceof ApiError && error.status === 409) {
      return {
        error: 'No puedes revisar tu propia correccion o ya fue revisada.',
        done: null,
      };
    }
    return {
      error: error instanceof ApiError ? error.message : 'No se pudo revisar la correccion.',
      done: null,
    };
  }

  revalidatePath(`/empresas/${companyId}/documentos/${artifactId}/mapeo`);
  return {
    error: null,
    done: decision === 'approved'
      ? 'Correccion aprobada. Sigue pendiente de aplicar en una version nueva.'
      : 'Correccion rechazada; el dataset base no fue modificado.',
  };
}

/** Aplica el conjunto aprobado completo a otra version, nunca al dataset base. */
export async function applyApprovedCorrectionsAction(
  _previous: CorrectionApplicationState,
  formData: FormData,
): Promise<CorrectionApplicationState> {
  const session = await readSession();
  if (!session) {
    redirect('/entrar');
  }
  const companyId = String(formData.get('companyId') ?? '');
  const artifactId = String(formData.get('artifactId') ?? '');
  const datasetVersionId = String(formData.get('datasetVersionId') ?? '');
  if (!companyId || !artifactId || !datasetVersionId) {
    return {
      error: 'El contexto del dataset esta incompleto; vuelve a cargar la pantalla.',
      done: null,
      resultDatasetVersionId: null,
    };
  }

  try {
    // Los IDs ocultos no son autoridad. Volvemos a ligar documento, estado y
    // conjunto de revisiones a lecturas autorizadas antes de ordenar la escritura.
    const [dataset, corrections] = await Promise.all([
      fetchDataset(session.token, companyId, datasetVersionId),
      fetchCorrections(session.token, companyId, datasetVersionId),
    ]);
    if (dataset.artifact_id !== artifactId || dataset.state !== 'validated') {
      return {
        error: 'La version visible ya no es un dataset validado aplicable.',
        done: null,
        resultDatasetVersionId: null,
      };
    }
    if (corrections.some((item) => item.status === 'pending_review')) {
      return {
        error: 'Todavia hay correcciones pendientes de revision independiente.',
        done: null,
        resultDatasetVersionId: null,
      };
    }
    if (!corrections.some((item) => item.status === 'approved')) {
      return {
        error: 'No hay correcciones aprobadas pendientes de aplicar.',
        done: null,
        resultDatasetVersionId: null,
      };
    }
    const result = await applyApprovedCorrections(
      session.token, companyId, datasetVersionId,
    );
    revalidatePath(`/empresas/${companyId}/documentos/${artifactId}/mapeo`);
    return {
      error: null,
      done:
        `${result.applied_correction_count} correccion(es) aplicada(s) en una ` +
        'version validada nueva. La version base permanece intacta.',
      resultDatasetVersionId: result.result_dataset_version_id,
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      redirect('/entrar');
    }
    if (error instanceof ApiError && error.status === 403) {
      return {
        error: 'Este rol no puede aplicar correcciones.',
        done: null,
        resultDatasetVersionId: null,
      };
    }
    if (error instanceof ApiError && error.status === 409) {
      return {
        error:
          'No se pudo derivar una version reproducible. Revisa el estado, el ' +
          'linaje y que ninguna propuesta haya cambiado.',
        done: null,
        resultDatasetVersionId: null,
      };
    }
    return {
      error: error instanceof ApiError ? error.message : 'No se pudieron aplicar las correcciones.',
      done: null,
      resultDatasetVersionId: null,
    };
  }
}

/** Rechazar conserva el motivo; nunca transforma el dataset ni borra evidencia. */
export async function rejectDatasetAction(
  _previous: ReviewState,
  formData: FormData,
): Promise<ReviewState> {
  const session = await readSession();
  if (!session) {
    redirect('/entrar');
  }
  const companyId = String(formData.get('companyId') ?? '');
  const artifactId = String(formData.get('artifactId') ?? '');
  const datasetVersionId = String(formData.get('datasetVersionId') ?? '');
  const reason = String(formData.get('reason') ?? '').trim();
  if (!reason) {
    return { error: 'Explica por que se rechaza el conjunto.', done: null };
  }
  if (reason.length > 200) {
    return { error: 'El motivo no puede superar 200 caracteres.', done: null };
  }

  try {
    const dataset = await fetchDataset(session.token, companyId, datasetVersionId);
    if (dataset.artifact_id !== artifactId) {
      return {
        error: 'El conjunto ya no pertenece al documento que estas revisando.',
        done: null,
      };
    }
    await rejectDataset(session.token, companyId, datasetVersionId, reason);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      redirect('/entrar');
    }
    if (error instanceof ApiError && error.status === 403) {
      return { error: 'Este rol no puede rechazar conjuntos.', done: null };
    }
    if (error instanceof ApiError && error.status === 422) {
      return {
        error: 'Esta version ya no puede rechazarse en su estado actual.',
        done: null,
      };
    }
    return {
      error:
        error instanceof ApiError ? error.message : 'No se pudo rechazar el conjunto.',
      done: null,
    };
  }

  revalidatePath(`/empresas/${companyId}/documentos/${artifactId}/mapeo`);
  return { error: null, done: 'Conjunto rechazado; el motivo quedo auditado.' };
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

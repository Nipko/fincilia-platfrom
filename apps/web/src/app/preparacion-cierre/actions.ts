'use server';

import { revalidatePath } from 'next/cache';
import { redirect } from 'next/navigation';

import {
  ApiError,
  closeAccountingPeriod,
  decideAccountingPeriodReopen,
  decideCloseReviewPacket,
  prepareCloseReviewPacket,
  requestAccountingPeriodReopen,
} from '@/lib/api';
import { readSession } from '@/lib/session';

export type CloseReviewActionState = {
  error: string | null;
  done: string | null;
};

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const KEY_PATTERN = /^[A-Za-z0-9._:-]{16,128}$/;
type CloseReviewDecision = 'evidence_reviewed' | 'changes_requested';

const REASONS: Record<CloseReviewDecision, ReadonlySet<string>> = {
  evidence_reviewed: new Set(['controls_reviewed']),
  changes_requested: new Set([
    'missing_evidence', 'inconsistent_scope', 'quality_blocker',
    'lineage_gap', 'reconciliation_gap',
  ]),
} as const;

function failure(error: unknown): CloseReviewActionState {
  if (!(error instanceof ApiError)) {
    return { error: 'No se pudo registrar la operacion. Intenta de nuevo.', done: null };
  }
  if (error.status === 403) {
    return {
      error: 'Tu acceso cambio o el expediente ya no esta disponible.', done: null,
    };
  }
  if (error.code === 'close-review-evidence-stale') {
    return {
      error: 'La evidencia cambio. El preparador debe crear una version nueva.', done: null,
    };
  }
  if (error.code === 'close-review-evidence-blocked') {
    return {
      error: 'La evidencia conserva bloqueos y no puede marcarse como revisada.', done: null,
    };
  }
  if (error.code === 'close-review-already-decided') {
    return { error: 'El expediente ya tiene una decision final.', done: null };
  }
  if (error.code === 'close-review-reviewer-ineligible') {
    return {
      error: 'El revisor asignado ya no conserva el rol requerido.', done: null,
    };
  }
  if (error.code === 'accounting-period-evidence-stale') {
    return {
      error: 'La evidencia cambio despues de la revision. Crea y revisa un expediente nuevo.',
      done: null,
    };
  }
  if (error.code === 'accounting-period-not-reviewed') {
    return { error: 'El expediente aun no tiene una revision positiva.', done: null };
  }
  if (error.code === 'accounting-period-reopen-already-decided') {
    return { error: 'La solicitud de reapertura ya tiene una decision final.', done: null };
  }
  if (error.status === 409) {
    return {
      error: 'El estado cambio, la clave ya se uso o la segregacion lo impide.', done: null,
    };
  }
  return {
    error: error.status === 422
      ? 'Los datos del expediente no son validos.'
      : 'No se pudo registrar la operacion. Intenta de nuevo.',
    done: null,
  };
}

export async function closeAccountingPeriodAction(
  _previous: CloseReviewActionState,
  formData: FormData,
): Promise<CloseReviewActionState> {
  const session = await readSession();
  if (!session) redirect('/entrar');
  const companyId = String(formData.get('companyId') ?? '');
  const packetId = String(formData.get('packetId') ?? '');
  const idempotencyKey = String(formData.get('idempotencyKey') ?? '');
  if (!UUID_PATTERN.test(companyId) || !UUID_PATTERN.test(packetId)
      || !KEY_PATTERN.test(idempotencyKey)) {
    return { error: 'El expediente de cierre no es valido.', done: null };
  }
  try {
    const result = await closeAccountingPeriod(
      session.token, companyId, packetId, idempotencyKey);
    revalidatePath('/preparacion-cierre');
    return {
      error: null,
      done: result.replayed
        ? `El cierre v${result.version} ya existia; no se duplico.`
        : `Periodo cerrado como version ${result.version}. Las nuevas escrituras quedaron bloqueadas.`,
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    return failure(error);
  }
}

const REOPEN_REASONS = new Set([
  'late_evidence', 'material_error', 'regulatory_adjustment',
  'scope_correction', 'other_documented',
]);

export async function requestAccountingPeriodReopenAction(
  _previous: CloseReviewActionState,
  formData: FormData,
): Promise<CloseReviewActionState> {
  const session = await readSession();
  if (!session) redirect('/entrar');
  const companyId = String(formData.get('companyId') ?? '');
  const closeId = String(formData.get('closeId') ?? '');
  const reasonCode = String(formData.get('reasonCode') ?? '');
  const rationale = String(formData.get('rationale') ?? '').trim();
  const idempotencyKey = String(formData.get('idempotencyKey') ?? '');
  if (!UUID_PATTERN.test(companyId) || !UUID_PATTERN.test(closeId)
      || !KEY_PATTERN.test(idempotencyKey) || !REOPEN_REASONS.has(reasonCode)
      || rationale.length < 10 || rationale.length > 500
      || Array.from(rationale).some((char) => char.charCodeAt(0) < 32)) {
    return { error: 'El motivo de reapertura no es valido.', done: null };
  }
  try {
    const result = await requestAccountingPeriodReopen(
      session.token, companyId, closeId, idempotencyKey,
      { reason_code: reasonCode, rationale });
    revalidatePath('/preparacion-cierre');
    return {
      error: null,
      done: result.replayed
        ? 'La solicitud ya existia; no se duplico.'
        : 'Solicitud de reapertura registrada para una segunda persona.',
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    return failure(error);
  }
}

const REOPEN_DECISIONS: Record<'approved' | 'rejected', ReadonlySet<string>> = {
  approved: new Set(['documented_basis_confirmed']),
  rejected: new Set(['insufficient_basis', 'wrong_scope', 'duplicate_request']),
};

export async function decideAccountingPeriodReopenAction(
  _previous: CloseReviewActionState,
  formData: FormData,
): Promise<CloseReviewActionState> {
  const session = await readSession();
  if (!session) redirect('/entrar');
  const companyId = String(formData.get('companyId') ?? '');
  const requestId = String(formData.get('requestId') ?? '');
  const decision = String(formData.get('decision') ?? '') as 'approved' | 'rejected';
  const reasonCode = String(formData.get('reasonCode') ?? '');
  const idempotencyKey = String(formData.get('idempotencyKey') ?? '');
  const reasons = REOPEN_DECISIONS[decision];
  if (!UUID_PATTERN.test(companyId) || !UUID_PATTERN.test(requestId)
      || !KEY_PATTERN.test(idempotencyKey) || !reasons || !reasons.has(reasonCode)) {
    return { error: 'La decision de reapertura no es valida.', done: null };
  }
  try {
    const result = await decideAccountingPeriodReopen(
      session.token, companyId, requestId, idempotencyKey,
      { decision, reason_code: reasonCode });
    revalidatePath('/preparacion-cierre');
    return {
      error: null,
      done: result.replayed
        ? 'La decision ya estaba registrada; no se duplico.'
        : decision === 'approved'
          ? 'Reapertura aprobada. El periodo vuelve a admitir trabajo financiero.'
          : 'Solicitud de reapertura rechazada; el periodo permanece cerrado.',
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    return failure(error);
  }
}

export async function prepareCloseReviewAction(
  _previous: CloseReviewActionState,
  formData: FormData,
): Promise<CloseReviewActionState> {
  const session = await readSession();
  if (!session) redirect('/entrar');
  const companyId = String(formData.get('companyId') ?? '');
  const periodStart = String(formData.get('periodStart') ?? '');
  const periodEnd = String(formData.get('periodEnd') ?? '');
  const reviewerId = String(formData.get('reviewerId') ?? '');
  const idempotencyKey = String(formData.get('idempotencyKey') ?? '');
  if (
    !UUID_PATTERN.test(companyId) || !UUID_PATTERN.test(reviewerId)
    || !DATE_PATTERN.test(periodStart) || !DATE_PATTERN.test(periodEnd)
    || periodEnd < periodStart || !KEY_PATTERN.test(idempotencyKey)
  ) {
    return { error: 'Selecciona un periodo y un revisor validos.', done: null };
  }
  try {
    const result = await prepareCloseReviewPacket(
      session.token, companyId, idempotencyKey, {
        period_start: periodStart,
        period_end: periodEnd,
        assigned_reviewer_id: reviewerId,
      });
    revalidatePath('/preparacion-cierre');
    return {
      error: null,
      done: result.replayed
        ? `El expediente v${result.version} ya existia; no se duplico.`
        : `Expediente v${result.version} fijado y asignado para revision.`,
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    return failure(error);
  }
}

export async function decideCloseReviewAction(
  _previous: CloseReviewActionState,
  formData: FormData,
): Promise<CloseReviewActionState> {
  const session = await readSession();
  if (!session) redirect('/entrar');
  const companyId = String(formData.get('companyId') ?? '');
  const packetId = String(formData.get('packetId') ?? '');
  const idempotencyKey = String(formData.get('idempotencyKey') ?? '');
  const decision = String(formData.get('decision') ?? '');
  const reasonCode = String(formData.get('reasonCode') ?? '');
  const reasons = REASONS[decision as CloseReviewDecision];
  if (
    !UUID_PATTERN.test(companyId) || !UUID_PATTERN.test(packetId)
    || !KEY_PATTERN.test(idempotencyKey)
    || !reasons || !reasons.has(reasonCode)
  ) {
    return { error: 'La decision o su motivo no son validos.', done: null };
  }
  try {
    const result = await decideCloseReviewPacket(
      session.token, companyId, packetId, idempotencyKey, {
        decision: decision as CloseReviewDecision,
        reason_code: reasonCode,
      });
    revalidatePath('/preparacion-cierre');
    return {
      error: null,
      done: result.replayed
        ? 'La misma decision ya estaba registrada; no se duplico.'
        : decision === 'evidence_reviewed'
          ? 'Revision de evidencia registrada. Esto no ejecuta ni certifica un cierre.'
          : 'Solicitud de cambios registrada en el expediente.',
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    return failure(error);
  }
}

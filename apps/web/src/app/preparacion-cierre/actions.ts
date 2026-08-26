'use server';

import { revalidatePath } from 'next/cache';
import { redirect } from 'next/navigation';

import {
  ApiError,
  decideCloseReviewPacket,
  prepareCloseReviewPacket,
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

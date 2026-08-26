'use client';

import { useActionState } from 'react';

import {
  decideCloseReviewAction,
  prepareCloseReviewAction,
  type CloseReviewActionState,
} from './actions';
import type { CloseReviewPacket, CloseReviewReviewer } from '@/lib/api';

const INITIAL: CloseReviewActionState = { error: null, done: null };

const CHANGE_REASONS = [
  ['missing_evidence', 'Falta evidencia'],
  ['inconsistent_scope', 'El alcance es inconsistente'],
  ['quality_blocker', 'Hay un bloqueo de calidad'],
  ['lineage_gap', 'Falta trazabilidad'],
  ['reconciliation_gap', 'Falta completar conciliacion'],
] as const;

function Feedback({ state }: { state: CloseReviewActionState }) {
  if (state.error) return <p className="notice error" role="alert">{state.error}</p>;
  if (state.done) return <p className="notice ok" role="status">{state.done}</p>;
  return null;
}

export function PrepareCloseReviewForm({
  companyId,
  periodStart,
  periodEnd,
  reviewers,
  commandKey,
}: {
  companyId: string;
  periodStart: string;
  periodEnd: string;
  reviewers: CloseReviewReviewer[];
  commandKey: string;
}) {
  const [state, action, pending] = useActionState(prepareCloseReviewAction, INITIAL);
  if (!reviewers.length) {
    return (
      <p className="meta" role="status">
        No hay otro revisor activo y elegible para este expediente.
      </p>
    );
  }
  return (
    <form className="close-review-form" action={action}>
      <input type="hidden" name="companyId" value={companyId} />
      <input type="hidden" name="periodStart" value={periodStart} />
      <input type="hidden" name="periodEnd" value={periodEnd} />
      <input type="hidden" name="idempotencyKey" value={commandKey} />
      <label>
        Revisor independiente
        <select name="reviewerId" required defaultValue={reviewers[0]?.subject_id}>
          {reviewers.map((reviewer) => (
            <option key={reviewer.subject_id} value={reviewer.subject_id}>
              {reviewer.display_name}
            </option>
          ))}
        </select>
      </label>
      <button type="submit" disabled={pending}>
        {pending ? 'Fijando evidencia...' : 'Crear expediente para revision'}
      </button>
      <Feedback state={state} />
    </form>
  );
}

function ReviewDecisionForm({
  companyId,
  packetId,
  decision,
  commandKey,
}: {
  companyId: string;
  packetId: string;
  decision: 'evidence_reviewed' | 'changes_requested';
  commandKey: string;
}) {
  const [state, action, pending] = useActionState(decideCloseReviewAction, INITIAL);
  const positive = decision === 'evidence_reviewed';
  return (
    <form className="close-review-decision" action={action}>
      <input type="hidden" name="companyId" value={companyId} />
      <input type="hidden" name="packetId" value={packetId} />
      <input type="hidden" name="idempotencyKey" value={commandKey} />
      <input type="hidden" name="decision" value={decision} />
      {positive ? (
        <input type="hidden" name="reasonCode" value="controls_reviewed" />
      ) : (
        <label>
          Motivo de los cambios
          <select name="reasonCode" required defaultValue="missing_evidence">
            {CHANGE_REASONS.map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
      )}
      <button type="submit" className={positive ? undefined : 'secondary'}
        disabled={pending}>
        {pending
          ? 'Registrando...'
          : positive
            ? 'Marcar evidencia revisada'
            : 'Solicitar cambios'}
      </button>
      <Feedback state={state} />
    </form>
  );
}

export function CloseReviewDecisionControls({
  companyId,
  packet,
  reviewCommandKey,
  changesCommandKey,
}: {
  companyId: string;
  packet: CloseReviewPacket;
  reviewCommandKey: string;
  changesCommandKey: string;
}) {
  return (
    <div className="close-review-actions">
      {packet.diagnostic_status === 'ready_for_review' ? (
        <ReviewDecisionForm companyId={companyId} packetId={packet.packet_id}
          decision="evidence_reviewed" commandKey={reviewCommandKey} />
      ) : (
        <p className="meta">
          Los controles bloqueados no pueden marcarse como evidencia revisada.
        </p>
      )}
      <ReviewDecisionForm companyId={companyId} packetId={packet.packet_id}
        decision="changes_requested" commandKey={changesCommandKey} />
    </div>
  );
}

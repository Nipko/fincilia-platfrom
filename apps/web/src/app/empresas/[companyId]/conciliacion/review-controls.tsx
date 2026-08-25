'use client';

import { useActionState } from 'react';

import {
  decideMatchAction,
  proposeMatchAction,
  type MatchReviewState,
} from '@/app/actions';
import type { MatchReview, ReconciliationCandidate } from '@/lib/api';

const INITIAL: MatchReviewState = { error: null, done: null };

const REASON_LABELS: Record<string, string> = {
  documented_counterpart: 'Contraparte documentada',
  documented_transfer: 'Transferencia documentada',
  reference_supported: 'Referencia respaldada',
  different_event: 'Corresponde a otro evento',
  timing_mismatch: 'La fecha no corresponde',
  wrong_counterpart: 'Contraparte incorrecta',
  insufficient_evidence: 'Evidencia insuficiente',
};

function formatTimestamp(value: string): string {
  // Igual en SSR y navegador: la zona local del contenedor no puede cambiar el
  // texto durante hidratacion. El sufijo hace explicito que no es hora local.
  return `${new Date(value).toISOString().slice(0, 16).replace('T', ' ')} UTC`;
}

function Feedback({ state }: { state: MatchReviewState }) {
  if (state.error) return <p className="notice error" role="alert">{state.error}</p>;
  if (state.done) return <p className="notice ok" role="status">{state.done}</p>;
  return null;
}

export function ProposeMatchForm({
  companyId,
  leftDatasetId,
  rightDatasetId,
  maxDays,
  candidate,
  commandKey,
}: {
  companyId: string;
  leftDatasetId: string;
  rightDatasetId: string;
  maxDays: number;
  candidate: ReconciliationCandidate;
  commandKey: string;
}) {
  const [state, action, pending] = useActionState(proposeMatchAction, INITIAL);
  return (
    <form className="match-review-form" action={action}>
      <input type="hidden" name="companyId" value={companyId} />
      <input type="hidden" name="leftDatasetId" value={leftDatasetId} />
      <input type="hidden" name="rightDatasetId" value={rightDatasetId} />
      <input type="hidden" name="leftMovementId" value={candidate.left.movement_id} />
      <input type="hidden" name="rightMovementId" value={candidate.right.movement_id} />
      <input type="hidden" name="maxDays" value={maxDays} />
      <input type="hidden" name="idempotencyKey" value={commandKey} />
      <button type="submit" disabled={pending}>
        {pending ? 'Registrando...' : 'Enviar a revision humana'}
      </button>
      <Feedback state={state} />
    </form>
  );
}

function DecisionForm({
  companyId,
  candidateId,
  decision,
  commandKey,
}: {
  companyId: string;
  candidateId: string;
  decision: 'confirmed' | 'rejected';
  commandKey: string;
}) {
  const [state, action, pending] = useActionState(decideMatchAction, INITIAL);
  const reasons = decision === 'confirmed'
    ? ['documented_counterpart', 'documented_transfer', 'reference_supported']
    : ['different_event', 'timing_mismatch', 'wrong_counterpart', 'insufficient_evidence'];
  return (
    <form className="match-review-form" action={action}>
      <input type="hidden" name="companyId" value={companyId} />
      <input type="hidden" name="candidateId" value={candidateId} />
      <input type="hidden" name="idempotencyKey" value={commandKey} />
      <input type="hidden" name="decision" value={decision} />
      <label>
        Motivo para {decision === 'confirmed' ? 'confirmar' : 'rechazar'}
        <select name="reasonCode" required defaultValue={reasons[0]}>
          {reasons.map((reason) => (
            <option value={reason} key={reason}>{REASON_LABELS[reason]}</option>
          ))}
        </select>
      </label>
      <button type="submit" className={decision === 'rejected' ? 'secondary' : undefined}
        disabled={pending}>
        {pending
          ? 'Registrando...'
          : decision === 'confirmed'
            ? 'Confirmar revision'
            : 'Rechazar candidato'}
      </button>
      <Feedback state={state} />
    </form>
  );
}

export function MatchReviewPanel({
  companyId,
  review,
  canConfirm,
  canReject,
  confirmCommandKey,
  rejectCommandKey,
}: {
  companyId: string;
  review: MatchReview;
  canConfirm: boolean;
  canReject: boolean;
  confirmCommandKey: string;
  rejectCommandKey: string;
}) {
  if (review.decision) {
    return (
      <section className={`match-review-status match-review-status--${review.status}`}
        id={`revision-${review.candidate_id}`}
        aria-label="Estado de revision">
        <strong>{review.status === 'confirmed' ? 'Revision confirmada' : 'Candidato rechazado'}</strong>
        <span>{REASON_LABELS[review.decision.reason_code] ?? review.decision.reason_code}</span>
        <span className="meta">
          {review.decision.decided_by_name} · {formatTimestamp(review.decision.decided_at)}
        </span>
        <span className="meta">Registro humano sin efecto financiero.</span>
      </section>
    );
  }

  if (review.confirmation_conflict) {
    return (
      <section className="match-review-status match-review-status--open"
        id={`revision-${review.candidate_id}`}
        aria-label="Conflicto de confirmacion">
        <strong>No se puede confirmar este par</strong>
        <span>Uno de los movimientos ya fue confirmado con otra contraparte.</span>
        <span className="meta">
          El expediente permanece abierto y visible. Puede rechazarse, pero no
          crear una segunda confirmacion para el mismo movimiento.
        </span>
        {canReject ? (
          <DecisionForm companyId={companyId} candidateId={review.candidate_id}
            decision="rejected" commandKey={rejectCommandKey} />
        ) : null}
      </section>
    );
  }

  return (
    <section className="match-review-status match-review-status--open"
      id={`revision-${review.candidate_id}`}
      aria-label="Estado de revision">
      <strong>Pendiente de decision humana</strong>
      <span className="meta">
        Propuesto por {review.proposed_by_name} · {formatTimestamp(review.proposed_at)}
      </span>
      {(canConfirm || canReject) ? (
        <div className="match-review-actions">
          {canConfirm ? (
            <DecisionForm companyId={companyId} candidateId={review.candidate_id}
              decision="confirmed" commandKey={confirmCommandKey} />
          ) : null}
          {canReject ? (
            <DecisionForm companyId={companyId} candidateId={review.candidate_id}
              decision="rejected" commandKey={rejectCommandKey} />
          ) : null}
        </div>
      ) : (
        <p className="meta">Tu rol puede consultar el expediente, pero no decidirlo.</p>
      )}
    </section>
  );
}

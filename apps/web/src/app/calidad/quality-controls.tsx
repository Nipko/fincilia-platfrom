'use client';

import { useActionState } from 'react';

import {
  scanQualityAction,
  triageQualityAction,
  type QualityActionState,
} from '@/app/actions';

const INITIAL: QualityActionState = { error: null, done: null };

function Feedback({ state }: { state: QualityActionState }) {
  if (state.error) return <p className="notice error" role="alert">{state.error}</p>;
  if (state.done) return <p className="notice ok" role="status">{state.done}</p>;
  return null;
}

export function ScanQualityForm({ companyId }: { companyId: string }) {
  const [state, action, pending] = useActionState(scanQualityAction, INITIAL);
  return (
    <form action={action} className="quality-scan-form">
      <input type="hidden" name="companyId" value={companyId} />
      <button type="submit" className="secondary" disabled={pending}>
        {pending ? 'Evaluando...' : 'Evaluar ahora'}
      </button>
      <Feedback state={state} />
    </form>
  );
}

function ReviewForm({
  companyId,
  issueId,
  status,
  label,
  reasons,
}: {
  companyId: string;
  issueId: string;
  status: 'acknowledged' | 'resolved' | 'dismissed';
  label: string;
  reasons: readonly { id: string; label: string }[];
}) {
  const [state, action, pending] = useActionState(triageQualityAction, INITIAL);
  return (
    <form action={action} className="quality-review-form">
      <input type="hidden" name="companyId" value={companyId} />
      <input type="hidden" name="issueId" value={issueId} />
      <input type="hidden" name="status" value={status} />
      {reasons.length === 1 ? (
        <input type="hidden" name="reasonCode" value={reasons[0]?.id} />
      ) : (
        <label>
          Motivo
          <select name="reasonCode" defaultValue={reasons[0]?.id} required>
            {reasons.map((reason) => (
              <option key={reason.id} value={reason.id}>{reason.label}</option>
            ))}
          </select>
        </label>
      )}
      <label>
        Comentario de revision
        <textarea name="rationale" minLength={10} maxLength={500} required
          placeholder="Describe que evidencia revisaste y por que tomas esta decision." />
      </label>
      <button type="submit" className={status === 'dismissed' ? 'secondary' : undefined}
        disabled={pending}>
        {pending ? 'Guardando...' : label}
      </button>
      <Feedback state={state} />
    </form>
  );
}

const RESOLVE_REASONS = [
  { id: 'reviewed_source', label: 'Fuente revisada' },
  { id: 'corrected_upstream', label: 'Corregido en origen' },
  { id: 'duplicate_confirmed', label: 'Duplicidad documentada' },
] as const;

const DISMISS_REASONS = [
  { id: 'expected_pattern', label: 'Patron esperado' },
  { id: 'false_positive', label: 'Falso positivo' },
  { id: 'not_applicable', label: 'No aplica' },
] as const;

export function QualityReviewControls({
  companyId,
  issueId,
  status,
}: {
  companyId: string;
  issueId: string;
  status: string;
}) {
  if (status === 'resolved' || status === 'dismissed') return null;
  return (
    <details className="quality-review">
      <summary>Revisar senal</summary>
      <div className="quality-review__forms">
        {status === 'open' ? (
          <ReviewForm companyId={companyId} issueId={issueId}
            status="acknowledged" label="Tomar caso"
            reasons={[{ id: 'investigate', label: 'Investigar' }]} />
        ) : null}
        <ReviewForm companyId={companyId} issueId={issueId}
          status="resolved" label="Resolver" reasons={RESOLVE_REASONS} />
        <ReviewForm companyId={companyId} issueId={issueId}
          status="dismissed" label="Descartar senal" reasons={DISMISS_REASONS} />
      </div>
    </details>
  );
}

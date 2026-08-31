'use client';

import { useActionState } from 'react';

import {
  closeAccountingPeriodAction,
  decideAccountingPeriodReopenAction,
  decideCloseReviewAction,
  prepareCloseReviewAction,
  requestAccountingPeriodReopenAction,
  type CloseReviewActionState,
} from './actions';
import type {
  AccountingPeriodClose,
  CloseReviewPacket,
  CloseReviewReviewer,
} from '@/lib/api';

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

export function CloseAccountingPeriodControl({
  companyId,
  packet,
  commandKey,
}: {
  companyId: string;
  packet: CloseReviewPacket;
  commandKey: string;
}) {
  const [state, action, pending] = useActionState(
    closeAccountingPeriodAction, INITIAL);
  return (
    <form className="close-review-decision" action={action}>
      <input type="hidden" name="companyId" value={companyId} />
      <input type="hidden" name="packetId" value={packet.packet_id} />
      <input type="hidden" name="idempotencyKey" value={commandKey} />
      <p className="meta">
        El cierre fija esta huella y bloqueara en PostgreSQL nuevas escrituras
        financieras que intersecten el periodo.
      </p>
      <button type="submit" disabled={pending}>
        {pending ? 'Cerrando periodo...' : 'Cerrar periodo contable'}
      </button>
      <Feedback state={state} />
    </form>
  );
}

const REOPEN_REASONS = [
  ['late_evidence', 'Evidencia recibida tarde'],
  ['material_error', 'Error material documentado'],
  ['regulatory_adjustment', 'Ajuste regulatorio'],
  ['scope_correction', 'Correccion de alcance'],
  ['other_documented', 'Otro motivo documentado'],
] as const;

export function RequestPeriodReopenForm({
  companyId,
  close,
  commandKey,
}: {
  companyId: string;
  close: AccountingPeriodClose;
  commandKey: string;
}) {
  const [state, action, pending] = useActionState(
    requestAccountingPeriodReopenAction, INITIAL);
  return (
    <form className="close-review-form" action={action}>
      <input type="hidden" name="companyId" value={companyId} />
      <input type="hidden" name="closeId" value={close.close_id} />
      <input type="hidden" name="idempotencyKey" value={commandKey} />
      <label>Motivo de reapertura<select name="reasonCode" required
        defaultValue="late_evidence">
        {REOPEN_REASONS.map(([value, label]) => (
          <option key={value} value={value}>{label}</option>
        ))}
      </select></label>
      <label>Justificacion documentada<textarea name="rationale" required
        minLength={10} maxLength={500} rows={3} /></label>
      <button type="submit" className="secondary" disabled={pending}>
        {pending ? 'Solicitando...' : 'Solicitar reapertura'}
      </button>
      <Feedback state={state} />
    </form>
  );
}

function ReopenDecisionForm({
  companyId,
  requestId,
  decision,
  commandKey,
}: {
  companyId: string;
  requestId: string;
  decision: 'approved' | 'rejected';
  commandKey: string;
}) {
  const [state, action, pending] = useActionState(
    decideAccountingPeriodReopenAction, INITIAL);
  const approve = decision === 'approved';
  return (
    <form className="close-review-decision" action={action}>
      <input type="hidden" name="companyId" value={companyId} />
      <input type="hidden" name="requestId" value={requestId} />
      <input type="hidden" name="decision" value={decision} />
      <input type="hidden" name="idempotencyKey" value={commandKey} />
      {approve ? (
        <input type="hidden" name="reasonCode" value="documented_basis_confirmed" />
      ) : (
        <label>Motivo<select name="reasonCode" required
          defaultValue="insufficient_basis">
          <option value="insufficient_basis">Fundamento insuficiente</option>
          <option value="wrong_scope">Alcance incorrecto</option>
          <option value="duplicate_request">Solicitud duplicada</option>
        </select></label>
      )}
      <button type="submit" className={approve ? undefined : 'secondary'}
        disabled={pending}>
        {pending ? 'Registrando...' : approve ? 'Aprobar reapertura' : 'Rechazar reapertura'}
      </button>
      <Feedback state={state} />
    </form>
  );
}

export function ReopenDecisionControls({
  companyId,
  close,
  approveCommandKey,
  rejectCommandKey,
}: {
  companyId: string;
  close: AccountingPeriodClose;
  approveCommandKey: string;
  rejectCommandKey: string;
}) {
  if (!close.reopen_request) return null;
  return (
    <div className="close-review-actions">
      <ReopenDecisionForm companyId={companyId}
        requestId={close.reopen_request.request_id} decision="approved"
        commandKey={approveCommandKey} />
      <ReopenDecisionForm companyId={companyId}
        requestId={close.reopen_request.request_id} decision="rejected"
        commandKey={rejectCommandKey} />
    </div>
  );
}

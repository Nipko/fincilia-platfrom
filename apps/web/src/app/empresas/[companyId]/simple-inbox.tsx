'use client';

import Link from 'next/link';
import { useActionState } from 'react';

import {
  alwaysApplyAction,
  applyRulesAction,
  revertRuleDecisionAction,
  simpleDecideAction,
  type AlwaysApplyState,
  type ApplyRulesState,
  type RevertState,
  type SimpleDecisionState,
} from '@/app/actions';
import { ReviewModeBadge } from '@/components/review-mode-badge';
import type { UnmatchedMovement } from '@/lib/api';
import type { SimplePair } from '@/lib/simple-mode';

/** Lo que la bandeja muestra de un cruce por decidir, ya preparado en el servidor. */
export type InboxDecisionItem = {
  key: string;
  candidateId: string | null;
  leftMovementId: string | null;
  rightMovementId: string | null;
  title: string;
  detail: string;
  explanation: string[];
  conflict: boolean;
  decisionKey: string;
  ruleKey: string;
};

export type InboxApplication = {
  decisionId: string;
  detail: string;
  revertKey: string;
};

const DECISION_INITIAL: SimpleDecisionState = {
  error: null, done: null, decisionId: null, decision: null, reviewMode: null,
};
const RULE_INITIAL: AlwaysApplyState = { error: null, done: null, ruleStatus: null };
const APPLY_INITIAL: ApplyRulesState = { error: null, done: null, applied: [], skippedCount: 0 };
const REVERT_INITIAL: RevertState = { error: null, done: null };

function Feedback({ error, done }: { error: string | null; done: string | null }) {
  if (error) return <p className="notice error" role="alert">{error}</p>;
  if (done) return <p className="notice ok" role="status">{done}</p>;
  return null;
}

function AlwaysApply({ companyId, decisionId, ruleKey }: {
  companyId: string; decisionId: string; ruleKey: string;
}) {
  const [state, action, pending] = useActionState(alwaysApplyAction, RULE_INITIAL);
  if (state.ruleStatus) {
    return <Feedback error={null} done={state.done} />;
  }
  return (
    <form action={action} className="always-apply">
      <input type="hidden" name="companyId" value={companyId} />
      <input type="hidden" name="decisionId" value={decisionId} />
      <input type="hidden" name="idempotencyKey" value={ruleKey} />
      <p className="meta">
        Si vuelve a aparecer un movimiento igual, una regla aprobada puede
        confirmarlo por ti. Siempre podrás deshacerlo.
      </p>
      <button type="submit" className="secondary" disabled={pending}>
        {pending ? 'Creando regla...' : '¿Aplicar siempre?'}
      </button>
      <Feedback error={state.error} done={null} />
    </form>
  );
}

function DecisionCard({ companyId, pair, item, canConfirm, canReject, canCreateRule }: {
  companyId: string;
  pair: SimplePair | null;
  item: InboxDecisionItem;
  canConfirm: boolean;
  canReject: boolean;
  canCreateRule: boolean;
}) {
  const [state, action, pending] = useActionState(simpleDecideAction, DECISION_INITIAL);
  const decided = state.decision !== null;
  return (
    <li className="card pending-item" data-inbox-item={item.key}>
      <div className="tags">
        <span className="tag tag--muted">Cruce</span>
        {decided ? <ReviewModeBadge mode={state.reviewMode} /> : null}
      </div>
      <h4>{item.title}</h4>
      <p className="meta">{item.detail}</p>
      {item.explanation.length ? (
        <ul aria-label="Por qué aparece">
          {item.explanation.map((line, index) => (
            <li key={`${item.key}:${index}`}>{line}</li>
          ))}
        </ul>
      ) : null}
      {item.conflict ? (
        <p className="meta">Uno de los movimientos ya está cruzado con otra partida.</p>
      ) : null}
      {!decided && (canConfirm || canReject) ? (
        <form action={action} className="match-review-actions">
          <input type="hidden" name="companyId" value={companyId} />
          <input type="hidden" name="idempotencyKey" value={item.decisionKey} />
          {item.candidateId ? (
            <input type="hidden" name="candidateId" value={item.candidateId} />
          ) : null}
          {!item.candidateId && pair && item.leftMovementId && item.rightMovementId ? (
            <>
              <input type="hidden" name="leftDatasetId" value={pair.leftDatasetId} />
              <input type="hidden" name="rightDatasetId" value={pair.rightDatasetId} />
              <input type="hidden" name="leftMovementId" value={item.leftMovementId} />
              <input type="hidden" name="rightMovementId" value={item.rightMovementId} />
            </>
          ) : null}
          {canConfirm && !item.conflict ? (
            <button type="submit" name="decision" value="confirmed" disabled={pending}>
              Confirmar
            </button>
          ) : null}
          {canReject ? (
            <button type="submit" name="decision" value="rejected" className="secondary"
              disabled={pending}>
              Rechazar
            </button>
          ) : null}
        </form>
      ) : null}
      <Feedback error={state.error} done={state.done} />
      {state.decisionId && canCreateRule ? (
        <AlwaysApply companyId={companyId} decisionId={state.decisionId} ruleKey={item.ruleKey} />
      ) : null}
    </li>
  );
}

export function RevertButton({ companyId, decisionId, revertKey }: {
  companyId: string; decisionId: string; revertKey: string;
}) {
  const [state, action, pending] = useActionState(revertRuleDecisionAction, REVERT_INITIAL);
  if (state.done) return <Feedback error={null} done={state.done} />;
  return (
    <form action={action} className="inline-form">
      <input type="hidden" name="companyId" value={companyId} />
      <input type="hidden" name="decisionId" value={decisionId} />
      <input type="hidden" name="idempotencyKey" value={revertKey} />
      <button type="submit" className="secondary" disabled={pending}>
        {pending ? 'Deshaciendo...' : 'Deshacer'}
      </button>
      <Feedback error={state.error} done={null} />
    </form>
  );
}

export function ApplyRulesControl({ companyId, pair, applyKey, revertKeyPrefix }: {
  companyId: string;
  pair: SimplePair;
  applyKey: string;
  revertKeyPrefix: string;
}) {
  const [state, action, pending] = useActionState(applyRulesAction, APPLY_INITIAL);
  return (
    <div className="apply-rules">
      <form action={action}>
        <input type="hidden" name="companyId" value={companyId} />
        <input type="hidden" name="leftDatasetId" value={pair.leftDatasetId} />
        <input type="hidden" name="rightDatasetId" value={pair.rightDatasetId} />
        <input type="hidden" name="idempotencyKey" value={applyKey} />
        <button type="submit" className="secondary" disabled={pending || state.done !== null}>
          {pending ? 'Aplicando...' : 'Aplicar reglas'}
        </button>
      </form>
      <Feedback error={state.error} done={state.done} />
      {state.applied.length ? (
        <ul className="pending-list" aria-label="Cruces aplicados por regla">
          {state.applied.map((item, index) => (
            <li className="card pending-item" key={item.decisionId}>
              <div className="tags"><ReviewModeBadge mode="approved_rule" /></div>
              <p className="meta">Cruce confirmado por una regla aprobada.</p>
              <RevertButton companyId={companyId} decisionId={item.decisionId}
                revertKey={`${revertKeyPrefix}.${index}`} />
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export type SimpleInboxProps = {
  companyId: string;
  pair: SimplePair | null;
  decisions: InboxDecisionItem[];
  applications: InboxApplication[];
  unpaired: UnmatchedMovement[];
  unpairedTotal: number;
  canConfirm: boolean;
  canReject: boolean;
  canPropose: boolean;
  canCreateRule: boolean;
  applyKey: string;
  revertKeyPrefix: string;
};

export function SimpleInbox(props: SimpleInboxProps) {
  const { companyId, pair } = props;
  const encoded = encodeURIComponent(companyId);
  return (
    <div className="simple-inbox">
      {props.decisions.length ? (
        <ul className="pending-list" aria-label="Cruces por decidir">
          {props.decisions.map((item) => (
            <DecisionCard key={item.key} companyId={companyId} pair={pair} item={item}
              canConfirm={props.canConfirm && (item.candidateId !== null || props.canPropose)}
              canReject={props.canReject && (item.candidateId !== null || props.canPropose)}
              canCreateRule={props.canCreateRule} />
          ))}
        </ul>
      ) : null}

      {pair && props.canPropose ? (
        <ApplyRulesControl companyId={companyId} pair={pair} applyKey={props.applyKey}
          revertKeyPrefix={props.revertKeyPrefix} />
      ) : null}

      {props.applications.length ? (
        <section aria-labelledby="rule-applications-heading">
          <h4 id="rule-applications-heading">Confirmados por reglas</h4>
          <ul className="pending-list" aria-label="Aplicaciones de reglas vigentes">
            {props.applications.map((item) => (
              <li className="card pending-item" key={item.decisionId}>
                <div className="tags"><ReviewModeBadge mode="approved_rule" /></div>
                <p className="meta">{item.detail}</p>
                {props.canReject ? (
                  <RevertButton companyId={companyId} decisionId={item.decisionId}
                    revertKey={item.revertKey} />
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {props.unpaired.length ? (
        <section aria-labelledby="unpaired-heading">
          <h4 id="unpaired-heading">Sin pareja todavía ({props.unpairedTotal})</h4>
          <ul className="pending-list" aria-label="Movimientos sin cruzar">
            {props.unpaired.map((movement) => (
              <li className="card pending-item" key={movement.movement_id}>
                <div className="tags">
                  <span className="tag tag--muted">
                    {movement.side === 'left' ? 'Archivo reciente' : 'Otro archivo'}
                  </span>
                </div>
                <p>{movement.description}</p>
                <p className="meta">
                  {movement.occurred_on} · {movement.amount} {movement.currency}
                </p>
              </li>
            ))}
          </ul>
          <Link href={`/empresas/${encoded}/conciliacion`}>Buscar pareja a mano →</Link>
        </section>
      ) : null}
    </div>
  );
}

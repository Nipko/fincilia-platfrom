'use client';

import { useActionState } from 'react';

import { ruleCommandAction, type RuleCommandState } from '@/app/actions';
import type { RuleAction } from '@/lib/simple-mode';

const INITIAL: RuleCommandState = { error: null, done: null };

const ACTION_LABELS: Record<RuleAction, string> = {
  approve: 'Aprobar',
  pause: 'Pausar',
  resume: 'Reanudar',
  retire: 'Retirar',
};

function RuleActionForm({ companyId, ruleId, action, commandKey }: {
  companyId: string;
  ruleId: string;
  action: RuleAction;
  commandKey: string;
}) {
  const [state, formAction, pending] = useActionState(ruleCommandAction, INITIAL);
  return (
    <form action={formAction} className="inline-form">
      <input type="hidden" name="companyId" value={companyId} />
      <input type="hidden" name="ruleId" value={ruleId} />
      <input type="hidden" name="action" value={action} />
      <input type="hidden" name="idempotencyKey" value={commandKey} />
      {state.done ? (
        <p className="notice ok" role="status">{state.done}</p>
      ) : (
        <button type="submit" disabled={pending}
          className={action === 'approve' || action === 'resume' ? undefined : 'secondary'}>
          {ACTION_LABELS[action]}
        </button>
      )}
      {state.error ? <p className="notice error" role="alert">{state.error}</p> : null}
    </form>
  );
}

export function RuleControls({ companyId, ruleId, actions, keys }: {
  companyId: string;
  ruleId: string;
  actions: RuleAction[];
  keys: Record<RuleAction, string>;
}) {
  if (!actions.length) return null;
  return (
    <div className="match-review-actions" role="group" aria-label="Acciones de la regla">
      {actions.map((action) => (
        <RuleActionForm key={action} companyId={companyId} ruleId={ruleId}
          action={action} commandKey={keys[action]} />
      ))}
    </div>
  );
}

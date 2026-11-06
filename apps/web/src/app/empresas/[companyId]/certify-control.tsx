'use client';

import { useActionState } from 'react';

import {
  certifyAccountingPeriodAction,
  type CertificationActionState,
} from '@/app/actions';

const INITIAL: CertificationActionState = { error: null, done: null };

export function CertifyCloseControl({
  companyId,
  closeId,
}: {
  companyId: string;
  closeId: string;
}) {
  const [state, action, pending] = useActionState(certifyAccountingPeriodAction, INITIAL);
  return (
    <form action={action}>
      <input type="hidden" name="companyId" value={companyId} />
      <input type="hidden" name="closeId" value={closeId} />
      <p className="meta">
        Al certificar confirmas que revisaste este cierre sin haberlo preparado
        ni cerrado tú.
      </p>
      <button type="submit" disabled={pending || state.done !== null}>
        {pending ? 'Certificando…' : 'Certificar cierre'}
      </button>
      {state.error ? <p className="notice error" role="alert">{state.error}</p> : null}
      {state.done ? <p className="notice ok" role="status">{state.done}</p> : null}
    </form>
  );
}

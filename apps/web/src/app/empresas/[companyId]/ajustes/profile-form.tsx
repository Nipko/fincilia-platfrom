'use client';

import { useActionState } from 'react';

import {
  changeOperatingProfileAction,
  type OperatingProfileActionState,
} from '@/app/actions';
import type { OperatingProfile } from '@/lib/api';
import {
  PROFILE_DESCRIPTIONS,
  PROFILE_LABELS,
  PROFILE_REASON_MAX,
  PROFILE_REASON_MIN,
} from '@/lib/simple-mode';

const INITIAL: OperatingProfileActionState = { error: null, done: null };
const PROFILES: OperatingProfile[] = ['simple', 'estricto'];

export function OperatingProfileForm({
  companyId,
  current,
}: {
  companyId: string;
  current: OperatingProfile;
}) {
  const [state, action, pending] = useActionState(changeOperatingProfileAction, INITIAL);
  return (
    <form className="form-grid" action={action}>
      <input type="hidden" name="companyId" value={companyId} />
      <fieldset className="team-size-options form-span-2">
        <legend>Perfil operativo</legend>
        {PROFILES.map((profile) => (
          <label key={profile}>
            <input type="radio" name="operatingProfile" value={profile}
                   defaultChecked={profile === current} required
                   aria-describedby={`profile-hint-${profile}`} />
            <span>
              <strong>{PROFILE_LABELS[profile]}</strong>
              <span className="field-help" id={`profile-hint-${profile}`}>
                {PROFILE_DESCRIPTIONS[profile]}
              </span>
            </span>
          </label>
        ))}
      </fieldset>
      <label className="form-span-2">
        Motivo del cambio
        <textarea name="reason" required minLength={PROFILE_REASON_MIN}
                  maxLength={PROFILE_REASON_MAX} rows={3}
                  aria-describedby="profile-reason-help" />
        <span className="field-help" id="profile-reason-help">
          Entre {PROFILE_REASON_MIN} y {PROFILE_REASON_MAX} caracteres. Queda en el historial.
        </span>
      </label>
      <div className="form-span-2">
        <button type="submit" disabled={pending}>
          {pending ? 'Guardando…' : 'Guardar perfil'}
        </button>
      </div>
      {state.error ? (
        <p className="notice error form-span-2" role="alert">{state.error}</p>
      ) : null}
      {state.done ? (
        <p className="notice ok form-span-2" role="status">{state.done}</p>
      ) : null}
    </form>
  );
}

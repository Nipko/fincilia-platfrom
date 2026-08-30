'use client';

import { useActionState } from 'react';

import { signInAction, type SignInState } from '../actions';

const INITIAL: SignInState = { error: null };

type LocalSignInFormProps = {
  showDemoAccounts: boolean;
};

export function LocalSignInForm({ showDemoAccounts }: LocalSignInFormProps) {
  const [state, action, pending] = useActionState(signInAction, INITIAL);
  return (
    <>
      <form className="signin" action={action}>
        <label>
          Usuario
          <input name="username" type="text" autoComplete="username"
                 defaultValue={showDemoAccounts ? 'ana@demo.local' : undefined}
                 placeholder={showDemoAccounts ? undefined : 'usuario@demo.local'} required />
        </label>
        <label>
          Contrasena
          <input name="secret" type="password" autoComplete="current-password" required />
        </label>
        {state.error ? <p className="notice error" role="alert">{state.error}</p> : null}
        <button type="submit" disabled={pending}>
          {pending ? 'Entrando...' : 'Entrar'}
        </button>
      </form>
      {showDemoAccounts ? (
        <details className="demo-access">
          <summary>Ver cuentas de demostracion</summary>
          <p className="hint">
            <code>ana@demo.local</code>, <code>beto@demo.local</code>,{' '}
            <code>carla@demo.local</code> y <code>sofia@demo.local</code>. La contrasena
            sintetica se crea en <code>db/seed/local.py</code>.
          </p>
        </details>
      ) : null}
    </>
  );
}

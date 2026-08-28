'use client';

import { useActionState } from 'react';

import { signInAction, type SignInState } from '../actions';

const INITIAL: SignInState = { error: null };

export function LocalSignInForm() {
  const [state, action, pending] = useActionState(signInAction, INITIAL);
  return (
    <>
      <form className="signin" action={action}>
        <label>
          Usuario
          <input name="username" type="text" autoComplete="username"
                 defaultValue="ana@demo.local" required />
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
      <details className="demo-access">
        <summary>Ver cuentas de demostracion</summary>
        <p className="hint">
          <code>ana@demo.local</code>, <code>beto@demo.local</code>,{' '}
          <code>carla@demo.local</code> y <code>sofia@demo.local</code>. La contrasena
          sintetica se crea en <code>db/seed/local.py</code>.
        </p>
      </details>
    </>
  );
}

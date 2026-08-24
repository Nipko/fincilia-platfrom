'use client';

import { useActionState } from 'react';

import { signInAction, type SignInState } from '../actions';

const INITIAL: SignInState = { error: null };

export default function SignInPage() {
  const [state, action, pending] = useActionState(signInAction, INITIAL);

  return (
    <main>
      <h1>Fincilia</h1>
      <p className="lede">Conciliacion y cierre. Entorno local con datos sinteticos.</p>

      <form className="signin" action={action}>
        <label>
          Usuario
          <input
            name="username"
            type="text"
            autoComplete="username"
            defaultValue="ana@demo.local"
            required
          />
        </label>
        <label>
          Contrasena
          <input name="secret" type="password" autoComplete="current-password" required />
        </label>
        {state.error ? (
          <p className="notice error" role="alert">
            {state.error}
          </p>
        ) : null}
        <div>
          <button type="submit" disabled={pending}>
            {pending ? 'Entrando...' : 'Entrar'}
          </button>
        </div>
      </form>

      <p className="hint">
        Los usuarios de demo son <code>ana@demo.local</code>, <code>beto@demo.local</code>,{' '}
        <code>carla@demo.local</code> y <code>sofia@demo.local</code>. La contrasena es
        sintetica y la crea <code>db/seed/local.py</code>.
      </p>
    </main>
  );
}

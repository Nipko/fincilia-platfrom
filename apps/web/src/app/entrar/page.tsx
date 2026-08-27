'use client';

import { useActionState } from 'react';

import { signInAction, type SignInState } from '../actions';

const INITIAL: SignInState = { error: null };

export default function SignInPage() {
  const [state, action, pending] = useActionState(signInAction, INITIAL);

  return (
    <main className="signin-page">
      <section className="signin-story" aria-labelledby="signin-title">
        <p className="eyebrow">Control financiero, sin perder el rastro</p>
        <h1 id="signin-title">Fincilia</h1>
        <p className="signin-story__lede">
          Ordena documentos, explica diferencias y prepara cada cierre desde un
          espacio compartido, visual y auditable.
        </p>
        <ul className="signin-benefits">
          <li>Varias empresas, una sola vista de trabajo</li>
          <li>Evidencia y linaje visibles en cada decision</li>
          <li>Datos sinteticos y aislamiento activo en este entorno</li>
        </ul>
      </section>

      <section className="signin-panel card" aria-labelledby="signin-form-title">
        <div>
          <p className="eyebrow">Bienvenido</p>
          <h2 id="signin-form-title">Entra a tu espacio</h2>
          <p className="meta">Usa una cuenta local para continuar.</p>
        </div>
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
      </section>
    </main>
  );
}

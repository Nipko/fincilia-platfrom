'use client';

import Link from 'next/link';
import { useActionState } from 'react';

import {
  registerAccountAction,
  type RegistrationState,
} from '../actions';

const INITIAL: RegistrationState = { error: null };

export function RegistrationForm({ inviteRequired }: { inviteRequired: boolean }) {
  const [state, action, pending] = useActionState(registerAccountAction, INITIAL);

  return (
    <main className="signin-page registration-page">
      <section className="signin-story" aria-labelledby="registration-title">
        <p className="eyebrow">Empieza con un espacio propio</p>
        <h1 id="registration-title">Crea tu cuenta</h1>
        <p className="signin-story__lede">
          Primero creamos tu identidad y tu firma. Despues configurarás la
          primera empresa, su cuenta, fuente documental y ciclo de trabajo.
        </p>
        <ol className="registration-steps">
          <li><strong>1.</strong> Cuenta y firma</li>
          <li><strong>2.</strong> Empresa y operacion inicial</li>
          <li><strong>3.</strong> Carga, limpieza y conciliacion</li>
        </ol>
      </section>

      <section className="signin-panel card" aria-labelledby="registration-form-title">
        <div>
          <p className="eyebrow">Laboratorio sintetico</p>
          <h2 id="registration-form-title">Datos de acceso</h2>
          <p className="meta">
            Usa nombres inventados y un correo terminado en <code>@demo.local</code>.
          </p>
        </div>

        <form className="signin" action={action} aria-describedby="registration-secret-help">
          <label>
            Código de invitación
            <input
              name="inviteCode"
              minLength={inviteRequired ? 24 : undefined}
              maxLength={128}
              required={inviteRequired}
              autoComplete="off"
              spellCheck={false}
              aria-describedby="registration-invite-help"
            />
          </label>
          <p className="field-help" id="registration-invite-help">
            {inviteRequired
              ? 'Cada invitación funciona una sola vez y no se almacena en claro.'
              : 'Opcional en el entorno local; obligatoria en la beta cerrada.'}
          </p>
          <label>
            Tu nombre visible
            <input name="displayName" minLength={2} maxLength={200} required
                   autoComplete="name" placeholder="Alex Contador Demo" />
          </label>
          <label>
            Nombre de tu firma o equipo
            <input name="firmName" minLength={2} maxLength={300} required
                   autoComplete="organization" placeholder="Firma Horizonte Demo" />
          </label>
          <label>
            Correo sintetico
            <input name="username" type="email" minLength={3} maxLength={120}
                   required autoComplete="username" placeholder="alex@demo.local" />
          </label>
          <label>
            Contrasena
            <input name="secret" type="password" minLength={14} maxLength={128}
                   required autoComplete="new-password" />
          </label>
          <label>
            Confirma la contrasena
            <input name="secretConfirmation" type="password" minLength={14}
                   maxLength={128} required autoComplete="new-password" />
          </label>
          <p className="field-help" id="registration-secret-help">
            Entre 14 y 128 caracteres, con mayuscula, minuscula, numero y simbolo.
            El navegador nunca recibe el token de sesion.
          </p>
          <fieldset className="registration-consent">
            <legend>Condiciones de esta beta</legend>
            <label>
              <input name="acceptSynthetic" type="checkbox" value="yes" required />
              <span>
                Entiendo que solo puedo usar nombres, correos, empresas, documentos
                y movimientos completamente inventados.
              </span>
            </label>
            <label>
              <input name="acceptTerms" type="checkbox" value="yes" required />
              <span>
                Acepto los <Link href="/terminos">terminos de la beta</Link> y he
                leido la <Link href="/privacidad">politica de privacidad</Link>.
              </span>
            </label>
          </fieldset>
          {state.error ? <p className="notice error" role="alert">{state.error}</p> : null}
          <button type="submit" disabled={pending}>
            {pending ? 'Creando cuenta…' : 'Crear cuenta y configurar empresa'}
          </button>
        </form>

        <div className="auth-switch">
          <span>¿Ya tienes una cuenta?</span>
          <Link href="/entrar">Volver a entrar</Link>
        </div>
      </section>
    </main>
  );
}

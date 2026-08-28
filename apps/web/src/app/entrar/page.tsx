import Link from 'next/link';

import { managedOidcEnabled } from '@/lib/managed-oidc';

import { LocalSignInForm } from './local-signin-form';

type SignInPageProps = {
  searchParams: Promise<{ error?: string | string[] }>;
};

const ERROR_MESSAGES: Record<string, string> = {
  'managed-rejected': 'No pudimos completar el ingreso. Reintenta con la cuenta invitada.',
  'managed-unavailable': 'El ingreso esta temporalmente fuera de servicio.',
};

export default async function SignInPage({ searchParams }: SignInPageProps) {
  const managed = managedOidcEnabled();
  const supplied = (await searchParams).error;
  const errorCode = Array.isArray(supplied) ? supplied[0] : supplied;
  const error = errorCode ? ERROR_MESSAGES[errorCode] : undefined;

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
          <li>Aislamiento por empresa y acceso nominal</li>
        </ul>
      </section>

      <section className="signin-panel card" aria-labelledby="signin-form-title">
        <div>
          <p className="eyebrow">Bienvenido</p>
          <h2 id="signin-form-title">Entra a tu espacio</h2>
          <p className="meta">
            {managed ? 'Usa la cuenta Google que recibio la invitacion.' :
              'Usa una cuenta local para continuar.'}
          </p>
        </div>
        {error ? <p className="notice error" role="alert">{error}</p> : null}
        {managed ? (
          <form method="post" action="/api/auth/oidc/start" className="managed-signin">
            <input type="hidden" name="mode" value="login" />
            <button type="submit" className="google-button">
              <span aria-hidden="true" className="google-mark">G</span>
              Continuar con Google
            </button>
          </form>
        ) : <LocalSignInForm />}

        <div className="auth-switch">
          <span>¿Es tu primera vez?</span>
          <Link className="button-link" href="/registro">Crear una cuenta</Link>
        </div>

        <p className="auth-legal">
          Al continuar aceptas los <Link href="/terminos">terminos de la beta</Link> y
          reconoces nuestra <Link href="/privacidad">politica de privacidad</Link>.
        </p>

      </section>
    </main>
  );
}

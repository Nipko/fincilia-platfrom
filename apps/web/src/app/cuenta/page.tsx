import Link from 'next/link';
import { redirect } from 'next/navigation';

import {
  ApiError,
  fetchBillingOverview,
  fetchBillingPlans,
  fetchManageableFirms,
  fetchMe,
} from '@/lib/api';
import { readSession } from '@/lib/session';
import { SignOut } from '@/app/empresas/sign-out';
import { BillingPanel } from './billing-panel';

export const dynamic = 'force-dynamic';

function formatMoment(epochSeconds: number): string {
  return new Intl.DateTimeFormat('es-CO', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'America/Bogota',
  }).format(new Date(epochSeconds * 1000));
}

export default async function AccountPage() {
  const session = await readSession();
  if (!session) redirect('/entrar');

  let me;
  try {
    me = await fetchMe(session.token);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    throw error;
  }

  const managed = me.identity_mode === 'managed_oidc';
  const [plans, firms] = await Promise.all([
    fetchBillingPlans(session.token),
    fetchManageableFirms(session.token),
  ]);
  const billing = await Promise.all(firms.map(async (firm) => ({
    firm,
    overview: await fetchBillingOverview(session.token, firm.firm_id),
  })));

  return (
    <main className="account-page">
      <header className="bar page-hero">
        <div className="page-heading">
          <p className="eyebrow">Identidad y acceso</p>
          <h1>Tu cuenta</h1>
          <p className="page-heading__description">
            Consulta tu sesión, empresas y responsabilidades sin exponer datos
            del proveedor de identidad.
          </p>
        </div>
        <SignOut />
      </header>

      <section className="identity-summary" aria-labelledby="identity-summary-title">
        <article className="card identity-profile">
          <span aria-hidden="true" className="account-avatar account-avatar--large">
            {me.display_name.slice(0, 1).toUpperCase()}
          </span>
          <div>
            <p className="eyebrow">Perfil</p>
            <h2 id="identity-summary-title">{me.display_name}</h2>
            <p className="meta">
              Identificador interno {me.subject_id.slice(0, 8)}…
            </p>
          </div>
        </article>

        <article className="card identity-status">
          <p className="eyebrow">Método de acceso</p>
          <h2>{managed ? 'Google mediante Cognito' : 'Cuenta local de demostración'}</h2>
          <p>
            {managed
              ? 'Google verifica la identidad; Fincilia resuelve empresas y roles en su servidor.'
              : 'Solo funciona con datos sintéticos. No es una credencial portable a producción.'}
          </p>
          <span className={`status-pill ${managed ? 'status-pill--ok' : ''}`}>
            {managed ? 'Identidad administrada' : 'Modo sintético'}
          </span>
        </article>

        <article className="card identity-session">
          <p className="eyebrow">Sesión actual</p>
          <h2>Activa</h2>
          <dl>
            <div><dt>Iniciada</dt><dd>{formatMoment(me.session_issued_at)}</dd></div>
            <div><dt>Vence</dt><dd>{formatMoment(me.session_expires_at)}</dd></div>
          </dl>
          <p className="meta">Los cambios de autorización se revalidan en el servidor.</p>
        </article>
      </section>

      <section className="workspace-section" aria-labelledby="account-companies-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Alcance vigente</p>
            <h2 id="account-companies-title">Empresas y responsabilidades</h2>
          </div>
          <Link href="/empresas">Abrir portafolio →</Link>
        </div>

        {me.companies.length === 0 ? (
          <p className="card">Tu cuenta no tiene acceso vigente a ninguna empresa.</p>
        ) : (
          <ul className="account-company-list">
            {me.companies.map((company) => {
              const canManage = company.roles.some(
                (role) => role === 'owner' || role === 'firm_admin',
              );
              return (
                <li className="card" key={company.company_id}>
                  <div>
                    <span aria-hidden="true" className="company-avatar">
                      {company.legal_name.slice(0, 1).toUpperCase()}
                    </span>
                    <div>
                      <h3>{company.legal_name}</h3>
                      <p className="meta">{company.country_code} · {company.status}</p>
                    </div>
                  </div>
                  <div className="tags" aria-label={`Roles en ${company.legal_name}`}>
                    {company.roles.map((role) => <span className="tag" key={role}>{role}</span>)}
                  </div>
                  <nav aria-label={`Acciones para ${company.legal_name}`}>
                    <Link href={`/empresas/${company.company_id}`}>Abrir empresa</Link>
                    {canManage ? (
                      <Link href={`/empresas/${company.company_id}/equipo`}>Gestionar equipo</Link>
                    ) : null}
                  </nav>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="card account-security-note" aria-labelledby="account-security-title">
        <div>
          <p className="eyebrow">Seguridad</p>
          <h2 id="account-security-title">La identidad no concede acceso financiero</h2>
          <p>
            Entrar demuestra quién eres. Cada empresa, rol y permiso se vuelve a
            resolver server-side y puede revocarse sin esperar a que termine la sesión.
          </p>
        </div>
        <Link href="/seguridad">Ver controles de seguridad</Link>
      </section>

      <section className="workspace-section" aria-labelledby="billing-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Capacidad y suscripción</p>
            <h2 id="billing-title">Planes de Fincilia</h2>
          </div>
          <span className="tag">Catálogo de evaluación</span>
        </div>
        {billing.length ? billing.map((item) => (
          <BillingPanel key={item.firm.firm_id} firm={item.firm}
            plans={plans} overview={item.overview} />
        )) : (
          <p className="card">Solo owners y administradores pueden gestionar el plan de una firma.</p>
        )}
      </section>
    </main>
  );
}

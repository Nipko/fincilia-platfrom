import { redirect } from 'next/navigation';

import {
  ApiError,
  fetchMe,
  fetchPlatformAudit,
  fetchPlatformDiagnostics,
  fetchPlatformIdentities,
  fetchPlatformOrganizations,
  fetchPlatformOverview,
} from '@/lib/api';
import { readSession } from '@/lib/session';

import { changeIdentityStatus, grantRole, revokeRole } from './actions';

export const dynamic = 'force-dynamic';

function moment(value: string): string {
  return new Intl.DateTimeFormat('es-CO', {
    dateStyle: 'medium', timeStyle: 'short', timeZone: 'America/Bogota',
  }).format(new Date(value));
}

export default async function PlatformPage() {
  const session = await readSession();
  if (!session) redirect('/entrar');

  let me: Awaited<ReturnType<typeof fetchMe>>;
  let overview: Awaited<ReturnType<typeof fetchPlatformOverview>>;
  let identities: Awaited<ReturnType<typeof fetchPlatformIdentities>>;
  let organizations: Awaited<ReturnType<typeof fetchPlatformOrganizations>>;
  let diagnostics: Awaited<ReturnType<typeof fetchPlatformDiagnostics>>;
  let audit: Awaited<ReturnType<typeof fetchPlatformAudit>>;
  try {
    me = await fetchMe(session.token);
    const canReadIdentities = me.platform_roles.some((role) => (
      role === 'platform_superadmin' || role === 'platform_operator'
    ));
    [overview, identities, organizations, diagnostics, audit] = await Promise.all([
        fetchPlatformOverview(session.token),
        canReadIdentities ? fetchPlatformIdentities(session.token) : Promise.resolve([]),
        fetchPlatformOrganizations(session.token),
        fetchPlatformDiagnostics(session.token),
        fetchPlatformAudit(session.token),
      ]);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    if (error instanceof ApiError && error.status === 403) redirect('/empresas');
    throw error;
  }
  const superadmin = me.platform_roles.includes('platform_superadmin');
  const canReadIdentities = superadmin || me.platform_roles.includes('platform_operator');

  return (
      <main className="platform-page">
        <header className="bar page-hero platform-hero">
          <div className="page-heading">
            <p className="eyebrow">Plano de control</p>
            <h1>Administración de Fincilia</h1>
            <p className="page-heading__description">
              Salud, identidades y organizaciones del servicio. Este rol no abre
              documentos, movimientos ni saldos de las empresas.
            </p>
          </div>
          <span className="status-pill status-pill--ok">UAT · acceso auditado</span>
        </header>

        <section className="platform-metrics" aria-label="Resumen de plataforma">
          <article className="card"><span>Personas</span><strong>{overview.subjects.total}</strong><small>{overview.subjects.active} activas</small></article>
          <article className="card"><span>Firmas</span><strong>{overview.firms.total}</strong><small>{overview.firms.active} activas</small></article>
          <article className="card"><span>Empresas</span><strong>{overview.companies.total}</strong><small>{overview.companies.active} activas</small></article>
          <article className="card"><span>Autoridades</span><strong>{overview.platform_roles}</strong><small>{overview.bootstrap_claimed ? 'bootstrap reclamado' : 'bootstrap pendiente'}</small></article>
        </section>

        <section className="workspace-section" aria-labelledby="platform-health-title">
          <div className="section-heading">
            <div><p className="eyebrow">Diagnóstico</p><h2 id="platform-health-title">Servicios y release</h2></div>
            <code>{diagnostics.release_id}</code>
          </div>
          <div className="platform-health-grid">
            {diagnostics.services.map((service) => (
              <article className="card" key={service.name}>
                <span className={`status-pill ${service.status === 'up' ? 'status-pill--ok' : 'status-pill--danger'}`}>{service.status}</span>
                <h3>{service.name}</h3>
                <p className="meta">{service.detail ?? 'sin detalle'}{service.latency_ms !== undefined ? ` · ${service.latency_ms} ms` : ''}</p>
              </article>
            ))}
          </div>
          <p className="platform-boundary">Break-glass: <strong>deshabilitado</strong>. El soporte financiero excepcional exige un flujo separado, temporal y con segundo aprobador.</p>
        </section>

        {canReadIdentities ? <section className="workspace-section" aria-labelledby="platform-users-title">
          <div className="section-heading"><div><p className="eyebrow">Identidad</p><h2 id="platform-users-title">Usuarios de la plataforma</h2></div><span>{identities.length} visibles</span></div>
          <div className="table-wrap"><table><thead><tr><th>Persona</th><th>Estado</th><th>Firmas</th><th>Autoridad</th><th>Acción</th></tr></thead><tbody>
            {identities.map((identity) => (
              <tr key={identity.subject_id}>
                <td><strong>{identity.display_name}</strong><small>{identity.subject_id.slice(0, 8)}… · {moment(identity.created_at)}</small></td>
                <td><span className={`status-pill ${identity.status === 'active' ? 'status-pill--ok' : 'status-pill--danger'}`}>{identity.status}</span></td>
                <td>{identity.active_firms}</td>
                <td>
                  {identity.platform_roles.length ? (
                    <div className="platform-role-list">
                      {identity.platform_roles.map((role) => (
                        <span className="tag" key={role}>{role}
                          {superadmin && identity.subject_id !== me.subject_id ? (
                            <form action={revokeRole}>
                              <input name="subject_id" type="hidden" value={identity.subject_id} />
                              <input name="platform_role" type="hidden" value={role} />
                              <button aria-label={`Revocar ${role} de ${identity.display_name}`} type="submit">×</button>
                            </form>
                          ) : null}
                        </span>
                      ))}
                    </div>
                  ) : '—'}
                  {superadmin && identity.subject_id !== me.subject_id ? (
                    <form action={grantRole} className="platform-role-grant">
                      <input name="subject_id" type="hidden" value={identity.subject_id} />
                      <select aria-label={`Nuevo rol para ${identity.display_name}`} name="platform_role" defaultValue="platform_operator">
                        <option value="platform_operator">Operador</option>
                        <option value="platform_auditor">Auditor</option>
                        <option value="platform_superadmin">Superadmin</option>
                      </select>
                      <button className="button-secondary" type="submit">Asignar</button>
                    </form>
                  ) : null}
                </td>
                <td>{superadmin && identity.subject_id !== me.subject_id ? (
                  <form action={changeIdentityStatus}>
                    <input name="subject_id" type="hidden" value={identity.subject_id} />
                    <input name="status" type="hidden" value={identity.status === 'active' ? 'suspended' : 'active'} />
                    <button className="button-secondary" type="submit">{identity.status === 'active' ? 'Suspender' : 'Reactivar'}</button>
                  </form>
                ) : <span className="meta">Sin acción</span>}</td>
              </tr>
            ))}
          </tbody></table></div>
        </section> : null}

        <section className="platform-columns">
          <div className="workspace-section">
            <div className="section-heading"><div><p className="eyebrow">Organizaciones</p><h2>Firmas registradas</h2></div></div>
            <ul className="platform-list">
              {organizations.map((organization) => (
                <li className="card" key={organization.firm_id}><div><strong>{organization.legal_name}</strong><small>{organization.active_members} miembros activos</small></div><span className="status-pill">{organization.status}</span></li>
              ))}
            </ul>
          </div>
          <div className="workspace-section">
            <div className="section-heading"><div><p className="eyebrow">Trazabilidad</p><h2>Últimas acciones</h2></div></div>
            <ol className="platform-list">
              {audit.map((event) => (
                <li className="card" key={event.event_id}><div><strong>{event.action}</strong><small>{event.actor_name} · {moment(event.occurred_at)}</small></div><span className="status-pill">{event.outcome}</span></li>
              ))}
              {audit.length === 0 ? <li className="card">Aún no hay acciones administrativas.</li> : null}
            </ol>
          </div>
        </section>
      </main>
  );
}

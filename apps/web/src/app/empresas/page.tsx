import Link from 'next/link';
import { redirect } from 'next/navigation';

import { ApiError, fetchMe } from '@/lib/api';
import {
  loadPortfolioSnapshots,
  type Metric,
  type PortfolioSnapshot,
} from '@/lib/portfolio';
import { readSession } from '@/lib/session';
import { SignOut } from './sign-out';

export const dynamic = 'force-dynamic';

function metricText<T>(
  metric: Metric<T>,
  render: (value: T) => string,
): string {
  if (metric.state === 'restricted') {
    return 'Sin acceso para este rol';
  }
  if (metric.state === 'unavailable') {
    return 'No disponible ahora';
  }
  return render(metric.value);
}

function CompanyCard({ snapshot }: { snapshot: PortfolioSnapshot }) {
  const { company } = snapshot;
  return (
    <li>
      <article className="card portfolio-card">
        <div className="portfolio-card__header">
          <div>
            <div className="company-name">{company.legal_name}</div>
            <div className="meta">
              {company.country_code} · {company.status}
            </div>
          </div>
          <Link
            aria-label={`Abrir ${company.legal_name}`}
            href={`/empresas/${company.company_id}`}
          >
            Abrir empresa
          </Link>
        </div>

        {snapshot.access !== 'available' ? (
          <p className="notice" role="status">
            {snapshot.access === 'revoked'
              ? 'El acceso cambio mientras se cargaba el portafolio.'
              : 'No se pudo actualizar esta empresa ahora.'}
          </p>
        ) : null}

        <dl className="metric-grid">
          <div>
            <dt>Documentos</dt>
            <dd>
              {metricText(
                snapshot.documents,
                (value) =>
                  `${value.visible} en ventana · ${value.quarantine} en cuarentena`,
              )}
            </dd>
          </div>
          <div>
            <dt>Preparacion</dt>
            <dd>
              {metricText(
                snapshot.datasets,
                (value) =>
                  `${value.pendingReview} por revisar · ${value.partial} parciales`,
              )}
            </dd>
          </div>
          <div>
            <dt>Ciclos</dt>
            <dd>
              {metricText(
                snapshot.expectations,
                (value) => `${value.overdue} vencidos · ${value.dueSoon} proximos`,
              )}
            </dd>
          </div>
        </dl>

        <div className="tags">
          {company.roles.map((role) => (
            <span className="tag" key={role}>
              {role}
            </span>
          ))}
        </div>
      </article>
    </li>
  );
}

export default async function CompaniesPage() {
  const session = await readSession();
  if (!session) {
    redirect('/entrar');
  }

  let me;
  try {
    me = await fetchMe(session.token);
  } catch (error) {
    // Un token caducado o invalidado por una revocacion no es un error de la
    // interfaz: es una sesion que termino. Se vuelve a pedir entrar.
    if (error instanceof ApiError && error.status === 401) {
      redirect('/entrar');
    }
    throw error;
  }

  let snapshots;
  try {
    snapshots = await loadPortfolioSnapshots(
      session.token,
      me.companies,
      new Date().toISOString().slice(0, 10),
    );
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      redirect('/entrar');
    }
    throw error;
  }

  return (
    <main>
      <header className="bar">
        <div>
          <h1>Portafolio de empresas</h1>
          <span className="who">{me.display_name}</span>
        </div>
        <SignOut />
      </header>

      <p className="lede">
        Carga operativa por empresa. Son conteos de trabajo, no saldos ni una
        evaluacion de salud financiera. Cada conteo usa la ventana acotada que
        expone hoy la API.
      </p>

      {snapshots.length === 0 ? (
        <p className="card">
          No hay ninguna empresa con acceso vigente para esta cuenta.
        </p>
      ) : (
        <ul className="companies">
          {snapshots.map((snapshot) => (
            <CompanyCard key={snapshot.company.company_id} snapshot={snapshot} />
          ))}
        </ul>
      )}
    </main>
  );
}

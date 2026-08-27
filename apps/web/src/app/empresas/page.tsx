import Link from 'next/link';
import { redirect } from 'next/navigation';

import { ApiError, fetchManageableFirms, fetchMe } from '@/lib/api';
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
            <div className="company-name">
              <span aria-hidden="true" className="company-avatar">
                {company.legal_name.slice(0, 1)}
              </span>
              <span>{company.legal_name}</span>
            </div>
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

  // El permiso de alta es una capacidad secundaria: una indisponibilidad
  // momentanea no puede derribar el portafolio que la persona ya puede leer.
  // Se falla cerrado ocultando el boton, nunca suponiendo que tiene permiso.
  let manageableFirms: Awaited<ReturnType<typeof fetchManageableFirms>> = [];
  try {
    manageableFirms = await fetchManageableFirms(session.token);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      redirect('/entrar');
    }
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
    <main className="portfolio-page">
      <header className="bar page-hero">
        <div className="page-heading">
          <p className="eyebrow">Espacio de trabajo</p>
          <h1>Portafolio de empresas</h1>
          <p className="page-heading__description">
            Prioriza lo pendiente y entra al contexto correcto antes de actuar.
          </p>
        </div>
        <div className="account-control">
          <span aria-hidden="true" className="account-avatar">
            {me.display_name.slice(0, 1).toUpperCase()}
          </span>
          <span className="who">{me.display_name}</span>
          <SignOut />
        </div>
      </header>

      <section className="workspace-section" aria-labelledby="portfolio-tools">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Vista multiempresa</p>
            <h2 id="portfolio-tools">Centros de trabajo</h2>
          </div>
          <p>Consulta transversal sin mezclar saldos ni decisiones entre empresas.</p>
        </div>
        <nav className="portfolio-actions" aria-label="Herramientas multiempresa">
        {manageableFirms.length > 0 ? (
          <Link aria-label="Crear una empresa" className="action-tile action-tile--primary" href="/empresas/nueva">
            <span aria-hidden="true" className="action-tile__icon">+</span>
            <strong>Crear una empresa</strong>
            <span>Configura el nuevo espacio de trabajo</span>
          </Link>
        ) : null}
          <Link aria-label="Abrir bandeja de revisiones multiempresa" className="action-tile" href="/revisiones">
            <span aria-hidden="true" className="action-tile__icon">✓</span>
            <strong>Revisiones</strong><span>Decisiones que esperan intervencion</span>
          </Link>
          <Link aria-label="Abrir ciclos y recordatorios" className="action-tile" href="/recordatorios">
            <span aria-hidden="true" className="action-tile__icon">◷</span>
            <strong>Ciclos</strong><span>Vencimientos y recordatorios</span>
          </Link>
          <Link aria-label="Abrir centro de calidad" className="action-tile" href="/calidad">
            <span aria-hidden="true" className="action-tile__icon">◇</span>
            <strong>Calidad</strong><span>Señales e informacion inconsistente</span>
          </Link>
          <Link aria-label="Abrir preparacion de cierre" className="action-tile" href="/preparacion-cierre">
            <span aria-hidden="true" className="action-tile__icon">◎</span>
            <strong>Preparar cierre</strong><span>Cobertura y evidencia por periodo</span>
          </Link>
          <Link aria-label="Abrir informes e historicos" className="action-tile" href="/informes">
            <span aria-hidden="true" className="action-tile__icon">↗</span>
            <strong>Informes</strong><span>Historicos y lectura operativa</span>
          </Link>
          <Link aria-label="Abrir accesos y auditoria" className="action-tile" href="/auditoria">
            <span aria-hidden="true" className="action-tile__icon">⌁</span>
            <strong>Auditoria</strong><span>Accesos y actividad trazable</span>
          </Link>
        </nav>
      </section>

      <div className="section-heading portfolio-list-heading">
        <div>
          <p className="eyebrow">Tu portafolio</p>
          <h2>Empresas activas</h2>
        </div>
        <p>
          Carga operativa, no saldos ni una evaluacion de salud financiera.
        </p>
      </div>

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

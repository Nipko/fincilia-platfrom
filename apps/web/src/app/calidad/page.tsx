import Link from 'next/link';
import { redirect } from 'next/navigation';

import { SignOut } from '@/app/empresas/sign-out';
import { ApiError, fetchMe, type QualityRule } from '@/lib/api';
import {
  aggregateQualitySummary,
  loadQualityCenter,
  parseQualitySeverity,
  parseQualityStatus,
  qualityHref,
  selectQualityCompanies,
  sortedQualityEntries,
  type QualitySeverityFilter,
  type QualityStatusFilter,
} from '@/lib/quality-center';
import { readSession } from '@/lib/session';
import { QualityReviewControls, ScanQualityForm } from './quality-controls';

export const dynamic = 'force-dynamic';

type QueryValue = string | string[] | undefined;

const STATUS_LABELS: Record<QualityStatusFilter, string> = {
  open: 'Abiertas',
  acknowledged: 'En investigacion',
  resolved: 'Resueltas',
  dismissed: 'Descartadas',
  all: 'Todas',
};

const SEVERITY_LABELS: Record<QualitySeverityFilter, string> = {
  high: 'Alta', warning: 'Advertencia', info: 'Informativa', all: 'Todas',
};

const RULE_CONTENT: Record<QualityRule, { title: string; detail: string }> = {
  dataset_completeness_mismatch: {
    title: 'Conteos del conjunto no coinciden',
    detail: 'La cantidad de registros esperada y la procesada necesitan revision.',
  },
  dataset_completeness_unknown: {
    title: 'Completitud aun no verificada',
    detail: 'El conjunto no tiene evidencia suficiente para declararse completo.',
  },
  dataset_rejected_records: {
    title: 'Registros rechazados',
    detail: 'Hay filas que no entraron al conjunto canonico y deben revisarse.',
  },
  lineage_invalidated: {
    title: 'Linaje invalidado',
    detail: 'La ruta a la evidencia dejo de cumplir el contrato vigente.',
  },
  duplicate_fingerprint: {
    title: 'Huella repetida',
    detail: 'Varias filas comparten rasgos exactos; no significa que sean el mismo hecho.',
  },
  reference_amount_conflict: {
    title: 'Referencia con datos contradictorios',
    detail: 'Una referencia normalizada aparece con atributos financieros distintos.',
  },
  posting_delay_over_31_days: {
    title: 'Fecha de registro inusual',
    detail: 'La distancia entre ocurrencia y registro supera 31 dias.',
  },
  amount_outlier_10x_median: {
    title: 'Volumen fuera del patron',
    detail: 'El valor supera diez veces la mediana exacta de una muestra suficiente.',
  },
};

function formatWhen(value: string): string {
  return new Intl.DateTimeFormat('es-CO', {
    dateStyle: 'medium', timeStyle: 'short', timeZone: 'America/Bogota',
  }).format(new Date(value));
}

export default async function QualityPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, QueryValue>>;
}) {
  const session = await readSession();
  if (!session) redirect('/entrar');
  const query = await searchParams;
  const status = parseQualityStatus(query.estado);
  const severity = parseQualitySeverity(query.severidad);

  let me;
  try {
    me = await fetchMe(session.token);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    throw error;
  }
  const companies = selectQualityCompanies(me.companies, query.empresa);
  const selectedCompany = companies.length === 1 ? companies[0]?.company_id : undefined;
  let snapshots;
  try {
    snapshots = await loadQualityCenter(session.token, companies, status, severity);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    throw error;
  }
  const entries = sortedQualityEntries(snapshots);
  const summary = aggregateQualitySummary(snapshots);
  const incomplete = snapshots.filter((snapshot) => snapshot.access !== 'available');
  const truncated = snapshots.filter((snapshot) => snapshot.page?.truncated);

  return (
    <main>
      <header className="bar">
        <div>
          <Link href="/empresas">← Portafolio</Link>
          <h1>Centro de calidad</h1>
          <span className="who">{me.display_name}</span>
        </div>
        <SignOut />
      </header>

      <p className="lede">
        Senales deterministas para revisar datos raros o inconsistentes. No son
        prueba de fraude, no cambian importes y no habilitan publicacion,
        conciliacion automatica, cierre ni informes certificados.
      </p>

      <section className="quality-toolbar" aria-label="Filtros de calidad">
        <form method="get" className="operations-company-filter">
          <input type="hidden" name="estado" value={status} />
          <input type="hidden" name="severidad" value={severity} />
          <label htmlFor="quality-company">Empresa</label>
          <select id="quality-company" name="empresa"
            defaultValue={selectedCompany ?? 'todas'}>
            <option value="todas">Todas las empresas autorizadas</option>
            {me.companies.map((company) => (
              <option key={company.company_id} value={company.company_id}>
                {company.legal_name}
              </option>
            ))}
          </select>
          <button type="submit" className="secondary">Aplicar</button>
        </form>
        <nav className="review-inbox-filters" aria-label="Estado de la senal">
          {(Object.keys(STATUS_LABELS) as QualityStatusFilter[]).map((item) => (
            <Link key={item} href={qualityHref(item, severity, selectedCompany)}
              aria-current={status === item ? 'page' : undefined}>
              {STATUS_LABELS[item]}
            </Link>
          ))}
        </nav>
        <nav className="review-inbox-filters" aria-label="Severidad">
          {(Object.keys(SEVERITY_LABELS) as QualitySeverityFilter[]).map((item) => (
            <Link key={item} href={qualityHref(status, item, selectedCompany)}
              aria-current={severity === item ? 'page' : undefined}>
              {SEVERITY_LABELS[item]}
            </Link>
          ))}
        </nav>
      </section>

      {incomplete.length ? (
        <section className="notice" role="status">
          <strong>Vista parcial.</strong> {incomplete.length} empresa(s) no se
          pudieron consultar o no conceden lectura. No se contabilizan como cero.
        </section>
      ) : null}
      {truncated.length ? (
        <section className="notice" role="status">
          La lista alcanzo 100 senales en {truncated.length} empresa(s). Los
          resumenes siguen viniendo de la base completa.
        </section>
      ) : null}

      <dl className="quality-summary" aria-label="Resumen de calidad">
        <div className="card quality-summary--high"><dt>Alta severidad</dt><dd>{summary.high}</dd></div>
        <div className="card quality-summary--open"><dt>Abiertas</dt><dd>{summary.open}</dd></div>
        <div className="card"><dt>En investigacion</dt><dd>{summary.acknowledged}</dd></div>
        <div className="card"><dt>Resueltas</dt><dd>{summary.resolved}</dd></div>
      </dl>

      <section className="quality-scans" aria-labelledby="quality-scan-title">
        <div>
          <h2 id="quality-scan-title">Evaluacion por empresa</h2>
          <p className="meta">Ventana acotada, reglas exactas y sin IA.</p>
        </div>
        <div className="quality-scan-list">
          {snapshots.filter((snapshot) => snapshot.access === 'available').map((snapshot) => (
            <div className="card quality-scan-company" key={snapshot.company.company_id}>
              <span>{snapshot.company.legal_name}</span>
              {snapshot.canManage ? (
                <ScanQualityForm companyId={snapshot.company.company_id} />
              ) : <span className="meta">Solo lectura</span>}
            </div>
          ))}
        </div>
      </section>

      <div className="candidate-heading">
        <div>
          <h2>{STATUS_LABELS[status]} · {SEVERITY_LABELS[severity]}</h2>
          <p className="meta">{entries.length} senales visibles</p>
        </div>
      </div>

      {entries.length === 0 ? (
        <p className="card" role="status">
          No hay senales visibles con estos filtros. Este vacio no certifica
          completitud, ausencia de fraude, conciliacion ni cierre.
        </p>
      ) : (
        <ol className="quality-list">
          {entries.map(({ company, canManage, issue }) => {
            const content = RULE_CONTENT[issue.rule_code];
            const evidenceHref = issue.scope_kind === 'movement'
              ? `/empresas/${company.company_id}/movimientos/${issue.scope_ref}`
              : `/empresas/${company.company_id}`;
            return (
              <li key={`${company.company_id}:${issue.issue_id}`}>
                <article className={`card quality-item quality-item--${issue.severity}`}>
                  <div className="quality-item__header">
                    <div>
                      <div className="tags">
                        <span className={`tag quality-severity--${issue.severity}`}>
                          {SEVERITY_LABELS[issue.severity]}
                        </span>
                        <span className="tag">{STATUS_LABELS[issue.status]}</span>
                      </div>
                      <h3>{content.title}</h3>
                      <p className="meta">{company.legal_name}</p>
                    </div>
                    <Link href={evidenceHref}>
                      {issue.scope_kind === 'movement' ? 'Ver movimiento y linaje' : 'Abrir empresa'}
                    </Link>
                  </div>
                  <p>{content.detail}</p>
                  <dl className="quality-details">
                    <div><dt>Regla</dt><dd>{issue.rule_version}</dd></div>
                    <div><dt>Observaciones</dt><dd>{issue.occurrence_count}</dd></div>
                    <div><dt>Ultima deteccion</dt><dd>{formatWhen(issue.last_seen_at)}</dd></div>
                    <div><dt>Responsable</dt><dd>{issue.assigned_to_name ?? 'Sin asignar'}</dd></div>
                  </dl>
                  {issue.reviewed_by_name ? (
                    <p className="meta">
                      Ultima revision por {issue.reviewed_by_name} · motivo{' '}
                      {issue.resolution_reason}
                    </p>
                  ) : null}
                  {canManage ? (
                    <QualityReviewControls companyId={company.company_id}
                      issueId={issue.issue_id} status={issue.status} />
                  ) : <p className="meta">Tu acceso permite leer, no gestionar esta senal.</p>}
                </article>
              </li>
            );
          })}
        </ol>
      )}
    </main>
  );
}

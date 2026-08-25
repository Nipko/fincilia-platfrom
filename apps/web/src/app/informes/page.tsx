import Link from 'next/link';
import { redirect } from 'next/navigation';

import { SignOut } from '@/app/empresas/sign-out';
import { ApiError, fetchMe, type ReportActivityPoint } from '@/lib/api';
import {
  aggregateOperationalCounts,
  loadReportCenter,
  parseReportDate,
  parseReportDays,
  reportHref,
  selectReportCompanies,
  type CompanyReportSnapshot,
} from '@/lib/reports';
import { readSession } from '@/lib/session';

export const dynamic = 'force-dynamic';

type QueryValue = string | string[] | undefined;

function monthLabel(value: string): string {
  return new Intl.DateTimeFormat('es-CO', {
    month: 'short', year: '2-digit', timeZone: 'UTC',
  }).format(new Date(`${value}T00:00:00Z`)).replace('.', '');
}

function exactMoney(value: string, currency: string): string {
  const [whole = '0', rawFraction = ''] = value.split('.');
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  const significant = rawFraction.replace(/0+$/, '');
  const fraction = significant.length === 0 ? '00' : significant.padEnd(2, '0');
  return `${currency} ${grouped},${fraction}`;
}

function ActivityChart({ points, companyName }: {
  points: ReportActivityPoint[];
  companyName: string;
}) {
  const max = Math.max(1, ...points.flatMap((point) => [
    point.documents, point.datasets, point.movements,
  ]));
  const width = 760;
  const height = 250;
  const plotHeight = 180;
  const groupWidth = Math.max(24, width / Math.max(points.length, 1));
  const barWidth = Math.max(3, Math.min(12, groupWidth / 4));
  const colors = ['var(--report-documents)', 'var(--report-datasets)', 'var(--report-movements)'];

  return (
    <figure className="report-chart">
      <figcaption>
        <strong>Actividad mensual</strong>
        <span className="meta"> Documentos, datasets y movimientos; son conteos.</span>
      </figcaption>
      <svg viewBox={`0 0 ${width} ${height}`} role="img"
        aria-label={`Actividad mensual de ${companyName}`}>
        <line x1="28" y1={plotHeight + 20} x2={width - 10} y2={plotHeight + 20}
          className="report-chart__axis" />
        {points.map((point, index) => {
          const x = 34 + index * groupWidth;
          const values = [point.documents, point.datasets, point.movements];
          return (
            <g key={point.month}>
              {values.map((value, kind) => {
                const barHeight = value / max * plotHeight;
                return <rect key={kind} x={x + kind * (barWidth + 2)}
                  y={plotHeight + 20 - barHeight} width={barWidth} height={barHeight}
                  fill={colors[kind]}><title>{value}</title></rect>;
              })}
              <text x={x} y={plotHeight + 42} className="report-chart__label">
                {monthLabel(point.month)}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="report-legend" aria-hidden="true">
        <span><i className="report-legend__documents" /> Documentos</span>
        <span><i className="report-legend__datasets" /> Datasets</span>
        <span><i className="report-legend__movements" /> Movimientos</span>
      </div>
    </figure>
  );
}

function CompanyReport({ snapshot, days, asOf }: {
  snapshot: CompanyReportSnapshot;
  days: 30 | 90 | 180 | 365;
  asOf: string | undefined;
}) {
  const { company, report } = snapshot;
  if (!report) {
    return (
      <article className="card report-company report-company--unavailable">
        <h2>{company.legal_name}</h2>
        <p role="status">
          {snapshot.access === 'restricted' || snapshot.access === 'revoked'
            ? 'Sin acceso vigente al informe. No se interpreta como cero actividad.'
            : 'No se pudo actualizar el informe de esta empresa.'}
        </p>
      </article>
    );
  }
  const { documents, datasets, reconciliation, quality } = report.summary;
  return (
    <article className="report-company" aria-labelledby={`report-${company.company_id}`}>
      <header className="report-company__header">
        <div>
          <p className="eyebrow">{report.range.start} — {report.range.end} · UTC</p>
          <h2 id={`report-${company.company_id}`}>{company.legal_name}</h2>
        </div>
        <div className="report-company__actions">
          <Link href={`/empresas/${company.company_id}`}>Abrir empresa</Link>
          {snapshot.canExport ? (
            <a className="button-link" href={reportHref(company.company_id, days, asOf)}>
              Descargar CSV
            </a>
          ) : <span className="meta">Sin permiso de exportacion</span>}
        </div>
      </header>

      <dl className="report-kpis">
        <div><dt>Documentos</dt><dd>{documents.total}</dd>
          <dd className="report-kpi-detail">{documents.quarantined} en cuarentena</dd></div>
        <div><dt>Datasets</dt><dd>{datasets.total}</dd>
          <dd className="report-kpi-detail">{datasets.published} publicados</dd></div>
        <div><dt>Filas procesadas</dt><dd>{datasets.records.toLocaleString('es-CO')}</dd>
          <dd className="report-kpi-detail">{datasets.rejected_records} rechazadas</dd></div>
        <div><dt>Por conciliar</dt><dd>{reconciliation.pending}</dd>
          <dd className="report-kpi-detail">{reconciliation.confirmed} confirmadas</dd></div>
        <div><dt>Alertas activas</dt><dd>{quality.open + quality.acknowledged}</dd>
          <dd className="report-kpi-detail">{quality.active_high} de severidad alta</dd></div>
      </dl>

      {(datasets.completeness_mismatch || datasets.completeness_unknown
        || datasets.lineage_invalidated) ? (
        <p className="notice" role="status">
          Requieren atencion: {datasets.completeness_mismatch} con conteos distintos,{' '}
          {datasets.completeness_unknown} sin completitud verificada y{' '}
          {datasets.lineage_invalidated} con linaje invalidado.
        </p>
      ) : null}

      <ActivityChart points={report.activity_series} companyName={company.legal_name} />

      <div className="report-grid">
        <section className="card" aria-label={`${company.legal_name}: volumen publicado por moneda`}>
          <h3 id={`money-${company.company_id}`}>Volumen publicado por moneda</h3>
          <p className="meta">
            Solo datasets publicados, verificados y con linaje completo. No es saldo.
          </p>
          {report.money_totals.length ? (
            <dl className="report-money-totals">
              {report.money_totals.map((total) => (
                <div key={total.currency}>
                  <dt>{total.currency} · {total.movement_count} movimientos</dt>
                  <dd><span>Entradas</span> {exactMoney(total.inflow_amount, total.currency)}</dd>
                  <dd><span>Salidas</span> {exactMoney(total.outflow_amount, total.currency)}</dd>
                </div>
              ))}
            </dl>
          ) : <p role="status">No hay volumen elegible en este rango.</p>}
        </section>

        <section className="card" aria-label={`${company.legal_name}: estado de preparacion`}>
          <h3 id={`state-${company.company_id}`}>Estado de preparacion</h3>
          <dl className="report-state-list">
            <div><dt>Borradores</dt><dd>{datasets.draft}</dd></div>
            <div><dt>Validados</dt><dd>{datasets.validated}</dd></div>
            <div><dt>Publicados</dt><dd>{datasets.published}</dd></div>
            <div><dt>Rechazados</dt><dd>{datasets.rejected}</dd></div>
          </dl>
          <Link href={`/calidad?empresa=${company.company_id}`}>Revisar calidad</Link>
        </section>
      </div>

      <details className="card report-detail-table">
        <summary>Ver tabla mensual exacta</summary>
        <div className="scroll">
          <table>
            <thead><tr><th scope="col">Mes</th><th scope="col">Moneda</th>
              <th scope="col">Movimientos</th><th scope="col">Entradas</th>
              <th scope="col">Salidas</th></tr></thead>
            <tbody>{report.money_series.map((point) => (
              <tr key={`${point.month}:${point.currency}`}>
                <th scope="row">{monthLabel(point.month)}</th><td>{point.currency}</td>
                <td>{point.movement_count}</td>
                <td>{exactMoney(point.inflow_amount, point.currency)}</td>
                <td>{exactMoney(point.outflow_amount, point.currency)}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </details>

      <section aria-label={`${company.legal_name}: datasets recientes`}>
        <h3 id={`recent-${company.company_id}`}>Datasets recientes</h3>
        {report.recent_datasets.length ? (
          <div className="card scroll"><table>
            <thead><tr><th scope="col">Preparado</th><th scope="col">Estado</th>
              <th scope="col">Completitud</th><th scope="col">Linaje</th>
              <th scope="col">Filas</th><th scope="col">Evidencia</th></tr></thead>
            <tbody>{report.recent_datasets.map((dataset) => (
              <tr key={dataset.dataset_version_id}>
                <th scope="row">{dataset.prepared_at.replace('T', ' ').slice(0, 16)}</th>
                <td>{dataset.state}</td><td>{dataset.completeness_state}</td>
                <td>{dataset.lineage_state}</td><td>{dataset.record_count}</td>
                <td><Link href={`/empresas/${company.company_id}/documentos/${dataset.artifact_id}`}>
                  Ver documento</Link></td>
              </tr>
            ))}</tbody>
          </table></div>
        ) : <p className="card" role="status">No hay datasets en este rango.</p>}
      </section>
    </article>
  );
}

export default async function ReportsPage({ searchParams }: {
  searchParams: Promise<Record<string, QueryValue>>;
}) {
  const session = await readSession();
  if (!session) redirect('/entrar');
  const query = await searchParams;
  const days = parseReportDays(query.dias);
  const asOf = parseReportDate(query.hasta);
  let me;
  try {
    me = await fetchMe(session.token);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    throw error;
  }
  const companies = selectReportCompanies(me.companies, query.empresa);
  const selected = companies.length === 1 ? companies[0]?.company_id : 'todas';
  let snapshots;
  try {
    snapshots = await loadReportCenter(session.token, companies, days, asOf);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    throw error;
  }
  const total = aggregateOperationalCounts(snapshots);
  const partial = snapshots.filter((snapshot) => snapshot.access !== 'available');

  return (
    <main>
      <header className="bar"><div><Link href="/empresas">← Portafolio</Link>
        <h1>Informes e historicos</h1><span className="who">{me.display_name}</span>
      </div><SignOut /></header>
      <p className="lede">
        Volumen operativo, tendencias y trazabilidad por empresa. Los importes no
        se mezclan entre empresas o monedas y este informe no certifica saldos ni cierre.
      </p>
      <form method="get" className="report-toolbar" aria-label="Rango del informe">
        <label>Empresa<select name="empresa" defaultValue={selected}>
          <option value="todas">Todas las empresas autorizadas</option>
          {me.companies.map((company) => <option key={company.company_id}
            value={company.company_id}>{company.legal_name}</option>)}
        </select></label>
        <label>Periodo<select name="dias" defaultValue={String(days)}>
          <option value="30">Ultimos 30 dias</option><option value="90">Ultimos 90 dias</option>
          <option value="180">Ultimos 180 dias</option><option value="365">Ultimos 365 dias</option>
        </select></label>
        <label>Hasta<input type="date" name="hasta" defaultValue={asOf ?? ''}
          max={new Date().toISOString().slice(0, 10)} /></label>
        <button type="submit">Actualizar</button>
      </form>
      {partial.length ? <p className="notice" role="status">
        Vista parcial: {partial.length} empresa(s) no pudieron consultarse. No se cuentan como cero.
      </p> : null}
      <dl className="report-portfolio-summary" aria-label="Resumen operativo multiempresa">
        <div><dt>Documentos</dt><dd>{total.documents}</dd></div>
        <div><dt>Datasets</dt><dd>{total.datasets}</dd></div>
        <div><dt>Movimientos</dt><dd>{total.movements.toLocaleString('es-CO')}</dd></div>
        <div><dt>Revisiones pendientes</dt><dd>{total.pendingReviews}</dd></div>
        <div><dt>Alertas altas</dt><dd>{total.activeHigh}</dd></div>
      </dl>
      <p className="meta report-aggregation-note">
        El resumen superior suma solo conteos operativos. Los importes permanecen separados por empresa.
      </p>
      <div className="report-company-list">
        {snapshots.map((snapshot) => <CompanyReport key={snapshot.company.company_id}
          snapshot={snapshot} days={days} asOf={asOf} />)}
      </div>
    </main>
  );
}

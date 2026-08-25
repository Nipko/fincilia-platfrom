import Link from 'next/link';
import { redirect } from 'next/navigation';

import { SignOut } from '@/app/empresas/sign-out';
import {
  ApiError,
  fetchMe,
  type CloseReadinessControl,
  type CloseReadinessPeriod,
} from '@/lib/api';
import {
  aggregateCloseReadinessCounts,
  formatClosePeriod,
  loadCloseReadinessCenter,
  selectCloseReadinessCompanies,
  type CloseReadinessSnapshot,
} from '@/lib/close-readiness';
import { readSession } from '@/lib/session';

export const dynamic = 'force-dynamic';

type QueryValue = string | string[] | undefined;

const CONTROL_LABELS: Record<string, string> = {
  expected_sources: 'Fuentes esperadas',
  expectations_satisfied: 'Ciclos recibidos',
  dataset_evidence: 'Evidencia procesada',
  published_datasets: 'Datasets publicados',
  verified_completeness: 'Completitud verificada',
  complete_lineage: 'Linaje completo',
  rejected_rows: 'Filas rechazadas',
  accounting_dates: 'Fechas contables',
  reconciliation_reviews: 'Revisiones de conciliacion',
  quality_alerts: 'Alertas altas',
  pending_corrections: 'Correcciones pendientes',
  account_balances: 'Saldos por cuenta',
  reconciliation_statements: 'Estado de conciliacion',
  product_close: 'Cierre productivo',
};

const STATE_LABELS: Record<CloseReadinessControl['state'], string> = {
  pass: 'Cumple',
  blocked: 'Bloquea',
  unavailable: 'Aun no disponible',
};

function PeriodCard({ period, companyId }: {
  period: CloseReadinessPeriod;
  companyId: string;
}) {
  return (
    <article className="card close-period">
      <header className="close-period__header">
        <div>
          <p className="eyebrow">Periodo contable</p>
          <h3>{formatClosePeriod(period.period_start, period.period_end)}</h3>
        </div>
        <span className="tag close-state close-state--blocked">No listo para cierre</span>
      </header>

      <dl className="close-control-grid">
        {period.controls.map((control) => (
          <div className={`close-control close-control--${control.state}`} key={control.code}>
            <dt>{CONTROL_LABELS[control.code] ?? control.code}</dt>
            <dd>{STATE_LABELS[control.state]}</dd>
            <dd className="close-control__count">
              {control.count} {control.count === 1 ? 'observacion' : 'observaciones'}
            </dd>
            <dd className="meta">{control.detail}</dd>
          </div>
        ))}
      </dl>

      <details className="close-evidence">
        <summary>
          Ver evidencia por fuente ({period.source_count} esperada(s),{' '}
          {period.selected_dataset_count} con dataset seleccionado)
        </summary>
        {period.sources.length ? (
          <div className="scroll">
            <table>
              <thead><tr><th scope="col">Fuente</th><th scope="col">Recepcion</th>
                <th scope="col">Dataset elegido</th><th scope="col">Completitud</th>
                <th scope="col">Linaje</th><th scope="col">Filas</th></tr></thead>
              <tbody>{period.sources.map((source) => (
                <tr key={source.expectation_id}>
                  <th scope="row">{source.source_name}</th>
                  <td>{source.expectation_state}</td>
                  <td>{source.dataset_state ?? 'Sin dataset'}</td>
                  <td>{source.completeness_state ?? 'Sin evaluar'}</td>
                  <td>{source.lineage_state ?? 'Sin evaluar'}</td>
                  <td>{source.movement_count} movimientos · {source.rejected_count} rechazadas</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : (
          <p role="status">No hay fuentes configuradas en esta ventana.</p>
        )}
      </details>

      <footer className="close-period__actions">
        <Link href={`/recordatorios?empresa=${companyId}`}>Revisar ciclos</Link>
        <Link href={`/calidad?empresa=${companyId}`}>Revisar calidad</Link>
        <Link href={`/revisiones?empresa=${companyId}`}>Revisar conciliaciones</Link>
      </footer>
    </article>
  );
}

function CompanyReadiness({ snapshot }: { snapshot: CloseReadinessSnapshot }) {
  const { company, result } = snapshot;
  if (!result) {
    return (
      <article className="card close-company close-company--unavailable">
        <h2>{company.legal_name}</h2>
        <p role="status">
          {snapshot.access === 'restricted' || snapshot.access === 'revoked'
            ? 'Sin acceso vigente al diagnostico. No se interpreta como cero bloqueos.'
            : 'No se pudo actualizar esta empresa. No se interpreta como lista para cierre.'}
        </p>
      </article>
    );
  }
  return (
    <section className="close-company" aria-labelledby={`close-${company.company_id}`}>
      <header className="close-company__header">
        <div>
          <p className="eyebrow">{result.source_count} fuente(s) en la ventana</p>
          <h2 id={`close-${company.company_id}`}>{company.legal_name}</h2>
        </div>
        <Link href={`/empresas/${company.company_id}`}>Abrir empresa</Link>
      </header>
      {result.items.length ? (
        <div className="close-period-list">
          {result.items.map((period) => (
            <PeriodCard key={`${period.period_start}:${period.period_end}`}
              period={period} companyId={company.company_id} />
          ))}
        </div>
      ) : (
        <p className="card" role="status">
          No hay periodos configurados en esta ventana. Esto no significa que la
          empresa este lista ni que exista un cierre certificado.
        </p>
      )}
    </section>
  );
}

export default async function CloseReadinessPage({ searchParams }: {
  searchParams: Promise<Record<string, QueryValue>>;
}) {
  const session = await readSession();
  if (!session) redirect('/entrar');
  const query = await searchParams;

  let me;
  try {
    me = await fetchMe(session.token);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    throw error;
  }
  const companies = selectCloseReadinessCompanies(me.companies, query.empresa);
  const selected = companies.length === 1 ? companies[0]?.company_id : 'todas';
  let snapshots;
  try {
    snapshots = await loadCloseReadinessCenter(session.token, companies);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    throw error;
  }
  const totals = aggregateCloseReadinessCounts(snapshots);
  const partial = snapshots.filter((snapshot) => snapshot.access !== 'available');

  return (
    <main>
      <header className="bar">
        <div><Link href="/empresas">← Portafolio</Link>
          <h1>Preparacion de cierre</h1><span className="who">{me.display_name}</span>
        </div>
        <SignOut />
      </header>

      <p className="lede">
        Centro de evidencia y bloqueos por empresa y periodo. Es un diagnostico
        explicable: no calcula saldos, no certifica conciliaciones y no ejecuta cierres.
      </p>
      <p className="notice close-readiness-warning" role="status">
        <strong>Todos los periodos permanecen bloqueados.</strong>{' '}
        El producto aun no materializa saldos por cuenta ni estados de conciliacion,
        y la operacion de cierre no esta habilitada.
      </p>

      <form method="get" className="close-toolbar" aria-label="Filtrar preparacion de cierre">
        <label>Empresa<select name="empresa" defaultValue={selected}>
          <option value="todas">Todas las empresas autorizadas</option>
          {me.companies.map((company) => (
            <option key={company.company_id} value={company.company_id}>
              {company.legal_name}
            </option>
          ))}
        </select></label>
        <button type="submit">Actualizar diagnostico</button>
      </form>

      {partial.length ? (
        <p className="notice" role="status">
          Vista parcial: {partial.length} empresa(s) no pudieron consultarse o ya no
          estan autorizadas. No se presentan como cero bloqueos.
        </p>
      ) : null}

      <dl className="close-summary" aria-label="Resumen diagnostico multiempresa">
        <div><dt>Periodos visibles</dt><dd>{totals.periods}</dd></div>
        <div><dt>Periodos bloqueados</dt><dd>{totals.blockedPeriods}</dd></div>
        <div><dt>Fuentes esperadas</dt><dd>{totals.sources}</dd></div>
        <div><dt>Revisiones abiertas</dt><dd>{totals.openReviews}</dd></div>
        <div><dt>Alertas altas</dt><dd>{totals.highAlerts}</dd></div>
        <div><dt>Correcciones pendientes</dt><dd>{totals.pendingCorrections}</dd></div>
      </dl>
      <p className="meta close-aggregation-note">
        El resumen suma solo conteos de trabajo. No combina importes, monedas ni saldos.
      </p>

      <div className="close-company-list">
        {snapshots.map((snapshot) => (
          <CompanyReadiness key={snapshot.company.company_id} snapshot={snapshot} />
        ))}
      </div>
    </main>
  );
}

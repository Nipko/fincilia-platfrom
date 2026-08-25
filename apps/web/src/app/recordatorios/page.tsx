import Link from 'next/link';
import { redirect } from 'next/navigation';

import { SignOut } from '@/app/empresas/sign-out';
import { ApiError, fetchMe, type OperationalReminderState } from '@/lib/api';
import {
  aggregateOperationalSummary,
  loadOperationsCenter,
  operationsHref,
  parseOperationsFilter,
  selectCompanies,
  sortedOperationalEntries,
  type OperationsFilter,
} from '@/lib/operations';
import { readSession } from '@/lib/session';

export const dynamic = 'force-dynamic';

type QueryValue = string | string[] | undefined;

const FILTER_LABELS: Record<OperationsFilter, string> = {
  atencion: 'Requieren atencion',
  vencidos: 'Vencidos',
  gracia: 'En gracia',
  hoy: 'Vencen hoy',
  proximos: 'Proximos 7 dias',
  futuros: 'Futuros',
  recibidos: 'Recibidos',
  dispensados: 'Dispensados',
  todos: 'Todo el historico',
};

const STATE_LABELS: Record<OperationalReminderState, string> = {
  overdue: 'Vencido',
  in_grace: 'En gracia',
  due_today: 'Vence hoy',
  due_soon: 'Proximo',
  upcoming: 'Programado',
  satisfied: 'Recibido',
  waived: 'Dispensado',
};

function timelineText(
  state: OperationalReminderState,
  daysLate: number,
  daysUntilDue: number | null,
  lateAfter: string,
): string {
  if (state === 'overdue') return `${daysLate} dia(s) de atraso despues de la gracia`;
  if (state === 'in_grace') return `Gracia vigente hasta ${lateAfter}`;
  if (state === 'due_today') return 'La fecha esperada es hoy';
  if (state === 'due_soon') return `Faltan ${daysUntilDue ?? 0} dia(s)`;
  if (state === 'upcoming') return `Programado para dentro de ${daysUntilDue ?? 0} dia(s)`;
  if (state === 'satisfied') return 'Documento recibido para este periodo';
  return 'Periodo dispensado con razon conservada';
}

export default async function OperationsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, QueryValue>>;
}) {
  const session = await readSession();
  if (!session) redirect('/entrar');
  const query = await searchParams;
  const filter = parseOperationsFilter(query.estado);

  let me;
  try {
    me = await fetchMe(session.token);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    throw error;
  }

  const selectedCompanies = selectCompanies(me.companies, query.empresa);
  const selectedCompany = selectedCompanies.length === 1
    ? selectedCompanies[0]?.company_id
    : undefined;
  let snapshots;
  try {
    snapshots = await loadOperationsCenter(
      session.token, selectedCompanies, filter,
    );
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    throw error;
  }

  const entries = sortedOperationalEntries(snapshots);
  const summary = aggregateOperationalSummary(snapshots);
  const incomplete = snapshots.filter((snapshot) => snapshot.access !== 'available');
  const truncated = snapshots.filter((snapshot) => snapshot.page?.has_more);
  const localDates = Array.from(new Set(snapshots.flatMap(
    (snapshot) => snapshot.page?.local_as_of_dates ?? [],
  ))).sort();

  return (
    <main>
      <header className="bar">
        <div>
          <Link href="/empresas">← Portafolio</Link>
          <h1>Centro de ciclos y recordatorios</h1>
          <span className="who">{me.display_name}</span>
        </div>
        <SignOut />
      </header>

      <p className="lede">
        Fechas y carga operativa consultadas empresa por empresa. Son avisos
        dentro de Fincilia: no prueban que se envio correo, que un saldo cuadre,
        que exista fraude o que un cierre este certificado.
      </p>

      <section className="operations-toolbar" aria-label="Filtros de ciclos">
        <form method="get" className="operations-company-filter">
          <input type="hidden" name="estado" value={filter} />
          <label htmlFor="operations-company">Empresa</label>
          <select id="operations-company" name="empresa"
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

        <nav className="review-inbox-filters" aria-label="Estado del recordatorio">
          {(Object.keys(FILTER_LABELS) as OperationsFilter[]).map((item) => (
            <Link key={item} href={operationsHref(item, selectedCompany)}
              aria-current={filter === item ? 'page' : undefined}>
              {FILTER_LABELS[item]}
            </Link>
          ))}
        </nav>
      </section>

      {incomplete.length ? (
        <section className="notice" role="status">
          <strong>Vista parcial.</strong>{' '}
          {incomplete.length} empresa(s) tienen acceso restringido, revocado o
          no estuvieron disponibles. No se contabilizan como cero pendientes.
        </section>
      ) : null}
      {truncated.length ? (
        <section className="notice" role="status">
          La ventana visible alcanzo 50 periodos en {truncated.length} empresa(s).
          Los totales de arriba vienen de la base completa; la lista inferior es
          deliberadamente acotada.
        </section>
      ) : null}

      <dl className="operations-summary" aria-label="Volumen operativo">
        <div className="card operations-summary__urgent">
          <dt>Vencidos</dt><dd>{summary.overdue}</dd>
        </div>
        <div className="card operations-summary__warning">
          <dt>Hoy o en gracia</dt><dd>{summary.due_today + summary.in_grace}</dd>
        </div>
        <div className="card">
          <dt>Proximos 7 dias</dt><dd>{summary.due_soon}</dd>
        </div>
        <div className="card">
          <dt>Recibidos historicos</dt><dd>{summary.satisfied}</dd>
        </div>
      </dl>

      <div className="candidate-heading">
        <div>
          <h2>{FILTER_LABELS[filter]}</h2>
          <p className="meta">
            {entries.length} visibles de {summary.filtered_total} en el filtro
            {localDates.length ? ` · fecha local ${localDates.join(' / ')}` : ''}
          </p>
        </div>
      </div>

      {entries.length === 0 ? (
        <p className="card" role="status">
          No hay periodos visibles para este filtro. Un vacio operativo no
          certifica completitud, conciliacion ni cierre.
        </p>
      ) : (
        <ol className="operations-list">
          {entries.map(({ company, period }) => (
            <li key={`${company.company_id}:${period.expectation_id}`}>
              <article className={`card operations-item operations-item--${period.reminder_state}`}>
                <div className="operations-item__header">
                  <div>
                    <span className={`tag reminder-state reminder-state--${period.reminder_state}`}>
                      {STATE_LABELS[period.reminder_state]}
                    </span>
                    <h3>{period.source_name}</h3>
                    <p className="meta">{company.legal_name}</p>
                  </div>
                  <Link href={`/empresas/${company.company_id}/fuentes/${period.data_source_id}#ciclo-esperado`}>
                    Abrir fuente
                  </Link>
                </div>
                <dl className="operations-details">
                  <div>
                    <dt>Periodo</dt>
                    <dd>{period.period_start} → {period.period_end}</dd>
                  </div>
                  <div><dt>Fecha esperada</dt><dd>{period.due_on}</dd></div>
                  <div>
                    <dt>Responsable</dt>
                    <dd>
                      {period.responsible_name ?? 'Sin responsable historico'}
                      {period.assigned_to_me ? ' · asignado a ti' : ''}
                    </dd>
                  </div>
                  <div><dt>Lectura operativa</dt><dd>{timelineText(
                    period.reminder_state, period.days_late,
                    period.days_until_due, period.late_after,
                  )}</dd></div>
                </dl>
                <p className="meta">
                  Evaluado al {period.local_as_of} en {period.timezone}.
                </p>
                {!period.responsible_eligible && period.responsible_subject_id ? (
                  <p className="notice" role="status">
                    El responsable historico ya no es elegible. El calendario se
                    conserva, pero debe reasignarse desde la fuente.
                  </p>
                ) : null}
              </article>
            </li>
          ))}
        </ol>
      )}
    </main>
  );
}

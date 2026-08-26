import Link from 'next/link';
import { redirect } from 'next/navigation';

import { SignOut } from '@/app/empresas/sign-out';
import { ApiError, fetchMe, type MatchReview } from '@/lib/api';
import { reconciliationUrl } from '@/lib/reconciliation';
import {
  formatReviewTimestamp,
  loadReviewInbox,
  parseReviewFilter,
  sortedReviewEntries,
  type ReviewInboxFilter,
} from '@/lib/review-inbox';
import { readSession } from '@/lib/session';

export const dynamic = 'force-dynamic';

type QueryValue = string | string[] | undefined;

const FILTER_LABELS: Record<ReviewInboxFilter, string> = {
  abiertas: 'Pendientes',
  confirmadas: 'Confirmadas',
  rechazadas: 'Rechazadas',
  todas: 'Todas',
};

const STATUS_LABELS: Record<MatchReview['status'], string> = {
  open: 'Pendiente',
  confirmed: 'Confirmada',
  rejected: 'Rechazada',
};

const SIGNAL_LABELS: Record<string, string> = {
  exact_amount: 'Monto exacto',
  same_currency: 'Misma moneda',
  opposite_direction: 'Direccion opuesta',
  different_financial_account: 'Cuentas distintas',
  date_within_explicit_window: 'Fecha en ventana',
  same_normalised_reference: 'Referencia coincidente',
};

function expedienteUrl(companyId: string, review: MatchReview): string {
  return `${reconciliationUrl(companyId, {
    leftDatasetId: review.left_dataset_id,
    rightDatasetId: review.right_dataset_id,
    maxDays: review.date_window_days,
    page: 0,
  })}#revision-${encodeURIComponent(review.candidate_id)}`;
}

export default async function ReviewsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, QueryValue>>;
}) {
  const session = await readSession();
  if (!session) redirect('/entrar');
  const filter = parseReviewFilter((await searchParams).estado);

  let me;
  try {
    me = await fetchMe(session.token);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    throw error;
  }

  let snapshots;
  try {
    snapshots = await loadReviewInbox(session.token, me.companies, filter);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    throw error;
  }
  const entries = sortedReviewEntries(snapshots);
  const incomplete = snapshots.filter((item) => item.access !== 'available');
  const truncated = snapshots.filter((item) => item.truncated);

  return (
    <main>
      <header className="bar">
        <div>
          <Link href="/empresas">← Portafolio</Link>
          <h1>Bandeja de revisiones</h1>
          <span className="who">{me.display_name}</span>
        </div>
        <SignOut />
      </header>

      <p className="lede">
        Trabajo de conciliacion visible empresa por empresa. No suma importes,
        no prueba saldos y no ejecuta cierres ni decisiones automaticas.
      </p>

      <nav className="review-inbox-filters" aria-label="Filtrar revisiones">
        {(Object.keys(FILTER_LABELS) as ReviewInboxFilter[]).map((item) => (
          <Link key={item} href={`/revisiones?estado=${item}`}
            aria-current={filter === item ? 'page' : undefined}>
            {FILTER_LABELS[item]}
          </Link>
        ))}
      </nav>

      {incomplete.length ? (
        <section className="notice" role="status">
          <strong>Vista parcial.</strong>{' '}
          {incomplete.length} empresa(s) no pudieron consultarse o ya no estan
          autorizadas. No se presentan como cero revisiones.
        </section>
      ) : null}
      {truncated.length ? (
        <section className="notice" role="status">
          Hay mas de 50 expedientes en {truncated.length} empresa(s). Esta vista
          conserva el limite por empresa; usa los filtros para reducir el trabajo.
        </section>
      ) : null}

      <div className="candidate-heading">
        <div>
          <h2>{FILTER_LABELS[filter]}</h2>
          <p className="meta">{entries.length} expediente(s) en la ventana visible</p>
        </div>
      </div>

      {entries.length === 0 ? (
        <p className="card" role="status">
          No hay expedientes visibles para este filtro. Esto no certifica que
          las empresas esten conciliadas.
        </p>
      ) : (
        <ol className="review-inbox-list">
          {entries.map(({ company, review }) => (
            <li key={`${company.company_id}:${review.candidate_id}`}>
              <article className="card review-inbox-item">
                <div className="review-inbox-item__header">
                  <div>
                    <span className={`tag review-state review-state--${review.status}`}>
                      {STATUS_LABELS[review.status]}
                    </span>
                    <h3>{company.legal_name}</h3>
                  </div>
                  <Link href={expedienteUrl(company.company_id, review)}>
                    Abrir expediente
                  </Link>
                </div>
                <dl className="review-inbox-details">
                  <div><dt>Propuesto por</dt><dd>{review.proposed_by_name}</dd></div>
                  <div><dt>Registrado</dt><dd>{formatReviewTimestamp(review.proposed_at)}</dd></div>
                  <div><dt>Distancia</dt><dd>{review.date_distance_days} dia(s)</dd></div>
                  <div><dt>Regla</dt><dd>{review.rule_version}</dd></div>
                </dl>
                <div className="tags" aria-label="Reglas explicables">
                  {review.signals.map((signal) => (
                    <span className="tag" key={signal}>
                      {SIGNAL_LABELS[signal] ?? signal}
                    </span>
                  ))}
                </div>
                <p className="meta">Registro humano sin efecto financiero.</p>
              </article>
            </li>
          ))}
        </ol>
      )}
    </main>
  );
}

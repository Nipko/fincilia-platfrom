import Link from 'next/link';
import { redirect } from 'next/navigation';

import { PageState } from '@/components/page-state';
import { SignOut } from '@/app/empresas/sign-out';
import { ApiError, fetchMe, type MatchReview } from '@/lib/api';
import { reconciliationReviewUrl } from '@/lib/reconciliation';
import {
  formatReviewTimestamp,
  loadReviewInbox,
  parseReviewFilter,
  parseReviewSelection,
  REVIEW_PAGE_SIZE,
  reviewInboxUrl,
  sortedReviewEntries,
  type ReviewInboxFilter,
  type ReviewInboxSelection,
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

function expedienteUrl(
  companyId: string,
  review: MatchReview,
  filter: ReviewInboxFilter,
  selection: ReviewInboxSelection,
): string {
  return reconciliationReviewUrl(companyId, {
    leftDatasetId: review.left_dataset_id,
    rightDatasetId: review.right_dataset_id,
    maxDays: review.date_window_days,
    referenceMode: 'all',
    page: 0,
  }, review.candidate_id, {
    filter,
    companyId: selection.companyId,
    page: selection.page,
  });
}

export default async function ReviewsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, QueryValue>>;
}) {
  const session = await readSession();
  if (!session) redirect('/entrar');
  const query = await searchParams;
  const filter = parseReviewFilter(query.estado);

  let me;
  try {
    me = await fetchMe(session.token);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    throw error;
  }

  const selection = parseReviewSelection(query, me.companies);
  const selectedCompanies = selection.valid
    ? selection.companyId
      ? me.companies.filter((company) => company.company_id === selection.companyId)
      : me.companies
    : [];
  let snapshots: Awaited<ReturnType<typeof loadReviewInbox>> = [];
  if (selection.valid) {
    try {
      snapshots = await loadReviewInbox(
        session.token,
        selectedCompanies,
        filter,
        selection.page * REVIEW_PAGE_SIZE,
        REVIEW_PAGE_SIZE,
      );
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) redirect('/entrar');
      throw error;
    }
  }
  const entries = sortedReviewEntries(snapshots);
  const incomplete = snapshots.filter((item) => item.access !== 'available');
  const truncated = snapshots.filter((item) => item.truncated);
  const nextPending = selection.valid && filter === 'abiertas' ? entries[0] : undefined;

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
          <Link key={item} href={reviewInboxUrl(item, selection.companyId)}
            aria-current={filter === item ? 'page' : undefined}>
            {FILTER_LABELS[item]}
          </Link>
        ))}
      </nav>

      <form className="card operations-company-filter review-company-filter" method="get">
        <input type="hidden" name="estado" value={filter} />
        <label htmlFor="review-company">Empresa</label>
        <select id="review-company" name="empresa"
          defaultValue={selection.companyId ?? 'todas'}>
          <option value="todas">Todas las empresas autorizadas</option>
          {me.companies.map((company) => (
            <option value={company.company_id} key={company.company_id}>
              {company.legal_name}
            </option>
          ))}
        </select>
        <button type="submit">Aplicar empresa</button>
      </form>

      {!selection.valid ? (
        <PageState
          kind="degraded"
          title="El filtro de empresa o pagina no es valido"
          description="La bandeja no amplio el alcance a todas las empresas. Restablece el filtro para continuar."
          action={<Link href={reviewInboxUrl(filter)}>Restablecer bandeja</Link>}
        />
      ) : null}

      {selection.valid && incomplete.length ? (
        <section className="notice" role="status">
          <strong>Vista parcial.</strong>{' '}
          {incomplete.length} empresa(s) no pudieron consultarse o ya no estan
          autorizadas. No se presentan como cero revisiones.
        </section>
      ) : null}
      {selection.valid && truncated.length ? (
        <section className="notice" role="status">
          {selection.companyId
            ? 'Hay mas expedientes en esta empresa. Usa la pagina siguiente para continuar.'
            : `Hay mas de ${REVIEW_PAGE_SIZE} expedientes en ${truncated.length} empresa(s). Selecciona una empresa para paginar sin mezclar alcances.`}
        </section>
      ) : null}

      {selection.valid && snapshots.length ? (
        <section className="review-workload" aria-labelledby="review-workload-title">
          <div className="candidate-heading">
            <div>
              <h2 id="review-workload-title">Carga visible por empresa</h2>
              <p className="meta">Conteo operativo del filtro actual; no representa importes ni saldos.</p>
            </div>
          </div>
          <ul className="review-workload-list">
            {snapshots.map((snapshot) => (
              <li className="card" key={snapshot.company.company_id}>
                <strong>{snapshot.company.legal_name}</strong>
                <span>{snapshot.access === 'available'
                  ? `${snapshot.items.length}${snapshot.truncated ? '+' : ''} expediente(s)`
                  : 'Consulta no disponible'}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <div className="candidate-heading">
        <div>
          <h2>{FILTER_LABELS[filter]}</h2>
          <p className="meta">
            {entries.length} expediente(s) en la ventana visible
            {selection.companyId ? ` · pagina ${selection.page + 1}` : ''}
          </p>
        </div>
        {nextPending ? (
          <Link className="button-link"
            href={expedienteUrl(
              nextPending.company.company_id, nextPending.review, filter, selection,
            )}>
            Abrir siguiente pendiente
          </Link>
        ) : null}
      </div>

      {!selection.valid ? null : entries.length === 0 ? (
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
                  <Link href={expedienteUrl(company.company_id, review, filter, selection)}>
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

      {selection.valid && selection.companyId && (selection.page > 0 || truncated.length) ? (
        <nav className="candidate-pagination" aria-label="Paginas de revisiones">
          {selection.page > 0 ? (
            <Link href={reviewInboxUrl(filter, selection.companyId, selection.page - 1)}>
              Pagina anterior
            </Link>
          ) : <span />}
          {truncated.length ? (
            <Link href={reviewInboxUrl(filter, selection.companyId, selection.page + 1)}>
              Pagina siguiente
            </Link>
          ) : <span />}
        </nav>
      ) : null}
    </main>
  );
}

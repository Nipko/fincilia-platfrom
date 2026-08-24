import Link from 'next/link';
import { redirect } from 'next/navigation';

import {
  ApiError,
  fetchCompany,
  fetchDatasets,
  fetchReconciliationCandidates,
  type CandidatePage,
  type DatasetSummary,
} from '@/lib/api';
import {
  CANDIDATE_PAGE_SIZE,
  formatExactMoney,
  reconciliationUrl,
  selectReconciliation,
} from '@/lib/reconciliation';
import { readSession } from '@/lib/session';
import { PageState } from '@/components/page-state';

export const dynamic = 'force-dynamic';

const SIGNAL_LABELS: Record<string, string> = {
  exact_amount: 'importe exacto',
  same_currency: 'misma moneda',
  opposite_direction: 'direccion opuesta',
  different_financial_account: 'cuentas distintas',
  date_within_explicit_window: 'fecha dentro de ventana',
  same_normalised_reference: 'misma referencia normalizada',
};

function datasetLabel(dataset: DatasetSummary): string {
  return `${dataset.prepared_at.slice(0, 10)} · ${dataset.movement_count} movimientos · ${dataset.state}`;
}

export default async function ReconciliationPage({
  params,
  searchParams,
}: {
  params: Promise<{ companyId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const session = await readSession();
  if (!session) redirect('/entrar');
  const [{ companyId }, query] = await Promise.all([params, searchParams]);

  let company;
  let datasets: DatasetSummary[];
  try {
    [company, datasets] = await Promise.all([
      fetchCompany(session.token, companyId),
      fetchDatasets(session.token, companyId),
    ]);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    if (error instanceof ApiError && (error.status === 403 || error.status === 404)) {
      return (
        <main>
          <PageState
            kind="denied"
            headingAs="h1"
            title="No puedes abrir esta conciliacion"
            description="La empresa o sus movimientos no estan disponibles para esta cuenta."
            action={<Link href="/empresas">Volver a empresas</Link>}
          />
        </main>
      );
    }
    throw error;
  }

  const selectable = datasets.filter(
    (dataset) => dataset.state === 'validated' || dataset.state === 'published',
  );
  const selection = selectReconciliation(
    query,
    selectable.map((dataset) => dataset.dataset_version_id),
  );
  let result: CandidatePage | null = null;
  let failure: 'scope' | 'invalid' | 'degraded' | null = null;
  if (selection.valid) {
    try {
      result = await fetchReconciliationCandidates(
        session.token,
        companyId,
        selection.leftDatasetId,
        selection.rightDatasetId,
        selection.maxDays,
        selection.page * CANDIDATE_PAGE_SIZE,
        CANDIDATE_PAGE_SIZE,
      );
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) redirect('/entrar');
      if (error instanceof ApiError && error.status === 403) failure = 'scope';
      else if (error instanceof ApiError && error.status === 422) failure = 'invalid';
      else if (error instanceof ApiError && error.status === 503) failure = 'degraded';
      else throw error;
    }
  }

  const previous = selection.page > 0
    ? reconciliationUrl(companyId, { ...selection, page: selection.page - 1 })
    : null;
  const next = result?.truncated
    ? reconciliationUrl(companyId, { ...selection, page: selection.page + 1 })
    : null;

  return (
    <main>
      <header className="bar">
        <div>
          <h1>Conciliacion visual</h1>
          <span className="who">{company.legal_name} · exploracion sintetica</span>
        </div>
        <nav aria-label="Navegacion de conciliacion">
          <Link href={`/empresas/${companyId}`}>Volver a la empresa</Link>{' '}
          <Link href="/empresas">Empresas</Link>
        </nav>
      </header>

      <section className="notice reconciliation-warning" role="note">
        <strong>Solo candidatos.</strong> Esta pantalla no confirma empates, no
        modifica movimientos y no demuestra que los saldos esten conciliados.
        Cada par debe revisarse desde su evidencia.
      </section>

      <form className="card reconciliation-filter" method="get">
        <label>
          Dataset izquierdo
          <select name="izquierda" defaultValue={selection.leftDatasetId} required>
            <option value="">Selecciona una version</option>
            {selectable.map((dataset) => (
              <option value={dataset.dataset_version_id} key={dataset.dataset_version_id}>
                {datasetLabel(dataset)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Dataset derecho
          <select name="derecha" defaultValue={selection.rightDatasetId} required>
            <option value="">Selecciona otra version</option>
            {selectable.map((dataset) => (
              <option value={dataset.dataset_version_id} key={dataset.dataset_version_id}>
                {datasetLabel(dataset)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Ventana maxima entre fechas
          <select name="ventana" defaultValue={String(selection.maxDays)}>
            <option value="0">Mismo dia</option>
            <option value="1">1 dia</option>
            <option value="3">3 dias</option>
            <option value="7">7 dias</option>
            <option value="15">15 dias</option>
            <option value="31">31 dias</option>
          </select>
        </label>
        <button type="submit">Buscar candidatos</button>
      </form>

      <section aria-labelledby="candidate-results-title">
        <div className="candidate-heading">
          <div>
            <h2 id="candidate-results-title">Pares candidatos</h2>
            <p className="meta">
              Importe y moneda exactos, direccion opuesta, cuentas distintas y
              fecha dentro de la ventana. La referencia solo explica y ordena.
            </p>
          </div>
          {result ? <span className="tag">pagina {selection.page + 1}</span> : null}
        </div>

        {selectable.length < 2 ? (
          <PageState
            kind="empty"
            title="Se necesitan dos datasets aptos"
            description="Prepara al menos dos versiones validadas o publicadas de cuentas distintas."
          />
        ) : selection.requested && !selection.valid ? (
          <PageState
            kind="degraded"
            title="La comparacion solicitada no es valida"
            description="Elige dos datasets distintos de esta empresa y una ventana entre 0 y 31 dias."
          />
        ) : failure === 'scope' ? (
          <PageState
            kind="denied"
            title="Los datasets no estan disponibles"
            description="Alguna version no pertenece a este alcance o aun no tiene completitud y linaje aptos."
          />
        ) : failure === 'invalid' ? (
          <PageState
            kind="degraded"
            title="La API rechazo la comparacion"
            description="Revisa los datasets, la ventana y la pagina solicitada."
          />
        ) : failure === 'degraded' ? (
          <PageState
            kind="degraded"
            title="El explorador no esta disponible"
            description="Esta capacidad solo funciona en el entorno sintetico autorizado."
          />
        ) : !selection.requested ? (
          <PageState
            kind="empty"
            title="Selecciona dos datasets"
            description="La busqueda comenzara cuando elijas las dos versiones que quieres cotejar."
          />
        ) : result?.candidates.length === 0 ? (
          <PageState
            kind="empty"
            title="No hay candidatos con estas reglas"
            description="Esto no demuestra que falten movimientos ni que los saldos esten conciliados. Prueba otra ventana o revisa las fuentes."
          />
        ) : (
          <div className="candidate-list" aria-label="Candidatos encontrados">
            {result?.candidates.map((candidate) => (
              <article
                className="candidate-pair card"
                key={`${candidate.left.movement_id}:${candidate.right.movement_id}`}
              >
                <div className="candidate-movement candidate-movement--left">
                  <span className="candidate-side">Dataset izquierdo</span>
                  <strong>{formatExactMoney(candidate.left.amount, candidate.left.currency)}</strong>
                  <span>{candidate.left.occurred_on} · {candidate.left.direction === 'outflow' ? 'salida' : 'entrada'}</span>
                  <span>{candidate.left.description}</span>
                  <span className="meta">Referencia: {candidate.left.reference ?? 'sin referencia'} · fila {candidate.left.record_ordinal}</span>
                  <Link href={`/empresas/${companyId}/movimientos/${candidate.left.movement_id}`}>
                    Ver evidencia izquierda
                  </Link>
                </div>
                <div className="candidate-signals">
                  <strong>{candidate.date_distance_days} dia(s)</strong>
                  <ul aria-label="Razones del candidato">
                    {candidate.signals.map((signal) => (
                      <li key={signal}>{SIGNAL_LABELS[signal] ?? signal}</li>
                    ))}
                  </ul>
                </div>
                <div className="candidate-movement candidate-movement--right">
                  <span className="candidate-side">Dataset derecho</span>
                  <strong>{formatExactMoney(candidate.right.amount, candidate.right.currency)}</strong>
                  <span>{candidate.right.occurred_on} · {candidate.right.direction === 'outflow' ? 'salida' : 'entrada'}</span>
                  <span>{candidate.right.description}</span>
                  <span className="meta">Referencia: {candidate.right.reference ?? 'sin referencia'} · fila {candidate.right.record_ordinal}</span>
                  <Link href={`/empresas/${companyId}/movimientos/${candidate.right.movement_id}`}>
                    Ver evidencia derecha
                  </Link>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      {(previous || next) ? (
        <nav className="candidate-pagination" aria-label="Paginas de candidatos">
          {previous ? <Link href={previous}>Pagina anterior</Link> : <span />}
          {next ? <Link href={next}>Pagina siguiente</Link> : <span />}
        </nav>
      ) : null}
    </main>
  );
}

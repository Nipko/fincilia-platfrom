import Link from 'next/link';
import { notFound, redirect } from 'next/navigation';

import {
  ApiError,
  fetchCompany,
  fetchDocumentHistory,
  fetchSourcesFull,
  type DocumentHistoryFilters,
  type DocumentHistoryItem,
  type Source,
} from '@/lib/api';
import { readSession } from '@/lib/session';
import { UploadForm } from '../upload';

export const dynamic = 'force-dynamic';

type Query = Record<string, string | string[] | undefined>;

const ZONES = new Set(['all', 'quarantine', 'raw']);
const PROCESSING_STATES = new Set([
  'all', 'not_started', 'queued', 'running', 'succeeded', 'failed',
]);

const ZONE_LABELS: Record<string, string> = {
  all: 'Todas las zonas', quarantine: 'Cuarentena', raw: 'Evidencia disponible',
};

const PROCESSING_LABELS: Record<string, string> = {
  all: 'Todos los estados',
  not_started: 'Sin iniciar',
  queued: 'En cola',
  running: 'Procesando',
  succeeded: 'Procesado',
  failed: 'Con error',
};

const PROMOTION_REASON_LABELS: Record<string, string> = {
  content_inspected: 'Contenido inspeccionado por completo',
  content_inspected_selection_required: 'Contenido seguro; seleccion de hoja requerida',
  sensitive_content: 'Informacion sensible detectada',
  no_scanner_for_format: 'Formato aun sin analizador seguro',
  macro_enabled_archive: 'Hoja de calculo con macros o scripts',
  active_workbook_content: 'Hoja de calculo con contenido activo',
  formula_review_required: 'Formulas pendientes de revision',
  worksheet_selection_required: 'Seleccion de hoja requerida',
  unsafe_or_malformed_workbook: 'Hoja de calculo danada o no segura',
  unsafe_or_active_pdf: 'PDF danado, cifrado o activo',
  ocr_required: 'PDF pendiente de OCR',
  unscannable: 'No fue posible examinar el contenido',
};

const RUN_KIND_LABELS: Record<string, string> = {
  scan: 'inspeccion', profile: 'perfilado', extract: 'extraccion',
  apply_overlay: 'aplicacion de correcciones',
};

function one(value: string | string[] | undefined): string {
  return typeof value === 'string' ? value : '';
}

function parseFilters(query: Query): DocumentHistoryFilters {
  const zone = one(query.zona);
  const processingStatus = one(query.proceso);
  const filename = one(query.nombre).trim().slice(0, 120);
  const cursor = one(query.cursor);
  const direction = one(query.direccion);
  const normalizedZone: NonNullable<DocumentHistoryFilters['zone']> =
    ZONES.has(zone) ? zone as NonNullable<DocumentHistoryFilters['zone']> : 'all';
  const normalizedProcessing: NonNullable<DocumentHistoryFilters['processingStatus']> =
    PROCESSING_STATES.has(processingStatus)
      ? processingStatus as NonNullable<DocumentHistoryFilters['processingStatus']>
      : 'all';
  const filters: DocumentHistoryFilters = {
    zone: normalizedZone,
    processingStatus: normalizedProcessing,
    direction: direction === 'previous' ? 'previous' : 'next',
    limit: 25,
  };
  const dataSourceId = one(query.fuente);
  if (dataSourceId) filters.dataSourceId = dataSourceId;
  if (filename) filters.filename = filename;
  if (cursor) filters.cursor = cursor;
  return filters;
}

function pageHref(
  companyId: string,
  filters: DocumentHistoryFilters,
  cursor: string,
  direction: 'next' | 'previous',
): string {
  const query = new URLSearchParams();
  if (filters.dataSourceId) query.set('fuente', filters.dataSourceId);
  if (filters.zone && filters.zone !== 'all') query.set('zona', filters.zone);
  if (filters.processingStatus && filters.processingStatus !== 'all') {
    query.set('proceso', filters.processingStatus);
  }
  if (filters.filename) query.set('nombre', filters.filename);
  query.set('cursor', cursor);
  query.set('direccion', direction);
  return `/empresas/${encodeURIComponent(companyId)}/documentos?${query}`;
}

function when(value: string): string {
  return new Intl.DateTimeFormat('es-CO', {
    dateStyle: 'medium', timeStyle: 'short', timeZone: 'America/Bogota',
  }).format(new Date(value));
}

function bytes(value: number): string {
  if (value < 1024) return `${value.toLocaleString('es-CO')} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toLocaleString('es-CO', {
    maximumFractionDigits: 1,
  })} KB`;
  return `${(value / (1024 * 1024)).toLocaleString('es-CO', {
    maximumFractionDigits: 1,
  })} MB`;
}

function processingDetail(item: DocumentHistoryItem): string {
  if (item.processing_status === 'failed') {
    return item.processing_error
      ? `Error ${item.processing_error}`
      : 'El ultimo proceso fallo';
  }
  if (!item.latest_run_kind) return 'Aun no tiene trabajo asociado';
  return `Ultimo trabajo: ${RUN_KIND_LABELS[item.latest_run_kind]
    ?? item.latest_run_kind}`;
}

function datasetDetail(item: DocumentHistoryItem): string {
  if (!item.dataset_version_id) return 'Sin version canonica';
  const counts = item.record_count === null
    ? ''
    : ` · ${item.record_count.toLocaleString('es-CO')} fila(s), ${(
      item.movement_count ?? 0
    ).toLocaleString('es-CO')} movimiento(s)`;
  return `${item.dataset_state ?? 'estado desconocido'} · ${
    item.completeness_state ?? 'completitud desconocida'
  }${counts}`;
}

function Restricted({ companyId }: { companyId: string }) {
  return (
    <main>
      <header className="bar">
        <h1>Sin acceso al centro de documentos</h1>
        <Link href={`/empresas/${companyId}`}>Volver a la empresa</Link>
      </header>
      <p className="card" role="status">
        Esta cuenta no tiene acceso vigente a documentos. No se presenta una
        lista vacia porque no tener permiso no demuestra que no existan entregas.
      </p>
    </main>
  );
}

export default async function DocumentCenterPage({
  params,
  searchParams,
}: {
  params: Promise<{ companyId: string }>;
  searchParams: Promise<Query>;
}) {
  const session = await readSession();
  if (!session) redirect('/entrar');
  const [{ companyId }, query] = await Promise.all([params, searchParams]);

  let company;
  try {
    company = await fetchCompany(session.token, companyId);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    if (error instanceof ApiError && error.status === 404) notFound();
    if (error instanceof ApiError && error.status === 403) {
      return <Restricted companyId={companyId} />;
    }
    throw error;
  }
  if (!company.permissions.includes('document.read')) {
    return <Restricted companyId={companyId} />;
  }

  const filters = parseFilters(query);
  const [historyResult, sourcesResult] = await Promise.allSettled([
    fetchDocumentHistory(session.token, companyId, filters),
    fetchSourcesFull(session.token, companyId),
  ] as const);

  if (historyResult.status === 'rejected') {
    const error: unknown = historyResult.reason;
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    if (error instanceof ApiError && error.status === 403) {
      return <Restricted companyId={companyId} />;
    }
    if (error instanceof ApiError && error.status === 422) {
      return (
        <main>
          <header className="bar">
            <h1>Filtro o pagina no validos</h1>
            <Link href={`/empresas/${companyId}/documentos`}>Restablecer vista</Link>
          </header>
          <p className="card notice error" role="alert">
            La direccion contiene un filtro o cursor que el servidor no acepta.
            Restablece la vista; no se consultaron datos fuera del alcance.
          </p>
        </main>
      );
    }
    throw error;
  }
  const history = historyResult.value;

  let sources: Source[] = [];
  let sourcesVisible = true;
  if (sourcesResult.status === 'fulfilled') {
    sources = sourcesResult.value;
  } else {
    const error: unknown = sourcesResult.reason;
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    if (error instanceof ApiError && error.status === 403) sourcesVisible = false;
    else throw error;
  }

  const resetHref = `/empresas/${companyId}/documentos`;
  const activeSources = sources.filter((source) => source.status === 'active');
  const uploadVisible = company.permissions.includes('document.upload') && sourcesVisible;
  const initialSourceId = activeSources.some(
    (source) => source.data_source_id === filters.dataSourceId,
  ) ? filters.dataSourceId ?? '' : '';
  return (
    <main>
      <header className="bar">
        <div>
          <Link href={`/empresas/${companyId}`}>← {company.legal_name}</Link>
          <h1>Centro de documentos</h1>
          <span className="who">
            Recepciones y procesamiento; no es un saldo ni una conciliacion.
          </span>
        </div>
        <nav aria-label="Navegacion del centro de documentos">
          {uploadVisible ? <><Link href="#cargar-documentos">Cargar archivos</Link>{' '}</> : null}
          <Link href={`/empresas/${companyId}/fuentes`}>Fuentes y cuentas</Link>
        </nav>
      </header>

      {uploadVisible ? (
        <section className="card document-upload-center" aria-labelledby="cargar-documentos">
          <div className="document-upload-copy">
            <h2 id="cargar-documentos">Cargar documentos</h2>
            <p className="meta">
              Elige una fuente y hasta 10 archivos. Cada recepcion se valida y
              confirma por separado; un fallo no deshace las demas.
            </p>
          </div>
          <UploadForm
            companyId={companyId}
            sources={activeSources}
            initialSourceId={initialSourceId}
          />
        </section>
      ) : null}

      <section className="card document-history-summary" aria-labelledby="document-summary">
        <h2 id="document-summary">Resultado de la consulta</h2>
        <dl className="metric-grid">
          <div><dt>Recepciones</dt><dd>{history.summary.total.toLocaleString('es-CO')}</dd></div>
          <div><dt>Disponibles</dt><dd>{history.summary.raw.toLocaleString('es-CO')}</dd></div>
          <div><dt>En cuarentena</dt><dd>{history.summary.quarantine.toLocaleString('es-CO')}</dd></div>
          <div><dt>Con error</dt><dd>{history.summary.failed.toLocaleString('es-CO')}</dd></div>
          <div><dt>Legacy sin fuente</dt><dd>{history.summary.legacy_unattributed.toLocaleString('es-CO')}</dd></div>
        </dl>
      </section>

      <form className="card document-history-filters" method="get"
        aria-label="Filtrar documentos">
        <label>
          Nombre contiene
          <input name="nombre" defaultValue={filters.filename ?? ''}
            placeholder="extracto-agosto.csv" maxLength={120} />
        </label>
        <label>
          Filtrar por fuente
          <select aria-label="Filtrar por fuente" name="fuente"
            defaultValue={filters.dataSourceId ?? ''}
            disabled={!sourcesVisible}>
            <option value="">Todas las fuentes</option>
            {sources.map((source) => (
              <option value={source.data_source_id} key={source.data_source_id}>
                {source.display_name}{source.status === 'active' ? '' : ` · ${source.status}`}
              </option>
            ))}
          </select>
        </label>
        <label>
          Zona efectiva
          <select name="zona" defaultValue={filters.zone ?? 'all'}>
            {Object.entries(ZONE_LABELS).map(([value, label]) => (
              <option value={value} key={value}>{label}</option>
            ))}
          </select>
        </label>
        <label>
          Procesamiento
          <select name="proceso" defaultValue={filters.processingStatus ?? 'all'}>
            {Object.entries(PROCESSING_LABELS).map(([value, label]) => (
              <option value={value} key={value}>{label}</option>
            ))}
          </select>
        </label>
        <div className="document-history-filter-actions">
          <button type="submit">Aplicar filtros</button>
          <Link href={resetHref}>Limpiar</Link>
        </div>
      </form>

      {!sourcesVisible ? (
        <p className="notice" role="status">
          El historico es visible, pero este rol no puede listar el catalogo de
          fuentes. El filtro de fuente queda deshabilitado, no se supone vacio.
        </p>
      ) : null}

      {history.items.length === 0 ? (
        <p className="card" role="status">
          No hay recepciones visibles para estos filtros. Prueba limpiarlos o
          carga documentos sinteticos desde esta misma pagina.
        </p>
      ) : (
        <div className="card scroll" tabIndex={0}
          aria-label="Tabla desplazable del historico documental">
          <table className="document-history-table">
            <caption className="meta">
              De la recepcion mas reciente a la mas antigua. Las cantidades son
              filas operativas; no se agregan importes ni valores de celdas.
            </caption>
            <thead><tr>
              <th scope="col">Documento y fuente</th>
              <th scope="col">Recibido</th>
              <th scope="col">Zona</th>
              <th scope="col">Procesamiento</th>
              <th scope="col">Version canonica</th>
            </tr></thead>
            <tbody>
              {history.items.map((item) => (
                <tr key={item.artifact_id}>
                  <th scope="row">
                    <Link href={`/empresas/${companyId}/documentos/${item.artifact_id}`}>
                      {item.filename}
                    </Link>
                    <span className="meta document-history-source">{item.source_name}</span>
                    <span className="meta">{bytes(item.byte_size)} · {item.media_type}</span>
                  </th>
                  <td className="when">{when(item.uploaded_at)}</td>
                  <td>
                    <span className={`outcome ${item.zone === 'quarantine' ? 'denied' : ''}`}>
                      {ZONE_LABELS[item.zone] ?? item.zone}
                    </span>
                    <span className="meta">
                      {item.promotion_reason
                        ? (PROMOTION_REASON_LABELS[item.promotion_reason]
                          ?? item.promotion_reason)
                        : 'Pendiente de decision de promocion'}
                    </span>
                  </td>
                  <td>
                    <span className={`outcome ${item.processing_status === 'failed' ? 'denied' : ''}`}>
                      {PROCESSING_LABELS[item.processing_status] ?? item.processing_status}
                    </span>
                    <span className="meta">{processingDetail(item)}</span>
                  </td>
                  <td>
                    {item.dataset_version_id ? (
                      <Link href={`/empresas/${companyId}/documentos/${item.artifact_id}`}>
                        {item.dataset_version_id.slice(0, 8)}
                      </Link>
                    ) : '—'}
                    <span className="meta">{datasetDetail(item)}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {(history.has_previous && history.previous_cursor)
        || (history.has_next && history.next_cursor) ? (
          <nav className="candidate-pagination" aria-label="Paginas de documentos">
            <span>
              {history.has_previous && history.previous_cursor ? (
                <Link href={pageHref(companyId, filters,
                  history.previous_cursor, 'previous')}>← Mas recientes</Link>
              ) : null}
            </span>
            <span>
              {history.has_next && history.next_cursor ? (
                <Link href={pageHref(companyId, filters,
                  history.next_cursor, 'next')}>Mas antiguos →</Link>
              ) : null}
            </span>
          </nav>
        ) : null}
    </main>
  );
}

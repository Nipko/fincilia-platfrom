import Link from 'next/link';
import { notFound, redirect } from 'next/navigation';

import {
  ApiError,
  fetchAccountsFull,
  fetchCompany,
  fetchCorrections,
  fetchDataset,
  fetchDatasets,
  fetchDocument,
  fetchMapping,
  fetchMappings,
  fetchMovements,
  fetchOverrides,
  fetchPreview,
  fetchSourcesFull,
  type Blocker,
  type DatasetDetail,
  type CorrectionProposal,
  type MappingDetail,
  type MappingSummary,
  type Movement,
  type PreviewPage,
  type RowOverrideSummary,
  type Source,
} from '@/lib/api';
import {
  CORRECTION_FIELD_LABELS,
  CORRECTION_STATUS_LABELS,
} from '@/lib/corrections';
import { isDatasetExportEligible } from '@/lib/export-policy';
import {
  pageFromQuery,
  selectDatasetVersion,
  selectMappingVersion,
  singleQueryValue,
  withFlowContext,
} from '@/lib/navigation';
import { readSession } from '@/lib/session';

import {
  ContinueForm,
  CorrectionReviewForm,
  DecisionForm,
  MappingForm,
  OverrideApprovalForm,
  PrepareForm,
  PublishForm,
  RejectDatasetForm,
} from './mapping-form';

export const dynamic = 'force-dynamic';

const TYPE_LABELS: Record<string, string> = {
  integer: 'entero',
  decimal_dot: 'decimal con punto',
  decimal_comma: 'decimal con coma',
  ambiguous_numeric: 'numero ambiguo',
  date_iso: 'fecha ISO',
  date_dmy: 'fecha dd/mm/aaaa',
  date_mdy: 'fecha mm/dd/aaaa',
  ambiguous_date: 'fecha ambigua',
  boolean: 'booleano',
  text: 'texto',
  empty: 'vacia',
};

const STATE_LABELS: Record<string, string> = {
  draft: 'borrador',
  staging: 'a medias',
  validated: 'validado',
  published: 'publicado',
  rejected: 'rechazado',
  cancelled: 'abandonado',
  superseded: 'sustituido',
};

const TRUNCATION_LABELS: Record<string, string> = {
  row_limit: 'se alcanzo el limite de filas',
  byte_limit: 'se alcanzo el limite de bytes',
  time_limit: 'se alcanzo el limite de tiempo',
};

const PUBLISH_BLOCKER_LABELS: Record<string, string> = {
  'permission-denied': 'Este rol no puede publicar conjuntos canonicos.',
  'dataset-not-validated': 'La version no esta validada y no se puede publicar.',
  'segregation-of-duties':
    'Quien preparo esta version no puede ser quien la publique.',
  'engine-release-not-approved':
    'La version del motor ya no esta aprobada; hay que preparar de nuevo.',
  'override-not-approved':
    'Hay una excepcion critica pendiente o que no coincide con lo publicado.',
  'correction-pending-review':
    'Hay una correccion tipada que necesita revision independiente.',
  'correction-not-applied':
    'Hay una correccion aprobada que todavia debe aplicarse en una version nueva.',
};

const FIELD_LABELS: Record<string, string> = {
  amount: 'Importe',
  currency: 'Moneda',
  direction: 'Direccion',
  accounting_date: 'Periodo contable',
  posting_date: 'Fecha de asiento',
  value_date: 'Fecha valor',
};

function money(amount: string, currency: string): string {
  // Punto fijo, sin `Number`: convertir a coma flotante para ensenar un importe
  // es perderlo en el unico sitio donde no se puede perder.
  const [whole = '0', fraction = ''] = amount.split('.');
  const trimmed = fraction.replace(/0+$/, '');
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return `${grouped}${trimmed ? `,${trimmed}` : ''} ${currency}`;
}

type AuthorizedLoad<T> =
  | { allowed: true; value: T }
  | { allowed: false };

async function loadAuthorized<T>(operation: Promise<T>): Promise<AuthorizedLoad<T>> {
  try {
    return { allowed: true, value: await operation };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      redirect('/entrar');
    }
    if (error instanceof ApiError && error.status === 403) {
      return { allowed: false };
    }
    if (error instanceof ApiError && error.status === 404) {
      notFound();
    }
    throw error;
  }
}

function AccessDenied({ companyId }: { companyId: string }) {
  return (
    <main>
      <header className="bar">
        <h1>Sin acceso</h1>
        <Link href={`/empresas/${companyId}`}>Volver</Link>
      </header>
      <p className="card">
        Esta cuenta no tiene acceso vigente a lo que has pedido. La respuesta no
        revela si el recurso existe.
      </p>
    </main>
  );
}

export default async function MappingPage({
  params,
  searchParams,
}: {
  params: Promise<{ companyId: string; artifactId: string }>;
  searchParams: Promise<{
    pagina?: string | string[];
    movimientosPagina?: string | string[];
    mapeo?: string | string[];
    fuente?: string | string[];
    dataset?: string | string[];
  }>;
}) {
  const session = await readSession();
  if (!session) {
    redirect('/entrar');
  }
  const { companyId, artifactId } = await params;
  const query = await searchParams;
  const page = pageFromQuery(query.pagina);
  const movementPage = pageFromQuery(query.movimientosPagina);
  const pageSize = 25;
  const movementPageSize = 50;
  const flowPath = `/empresas/${companyId}/documentos/${artifactId}/mapeo`;

  let company;
  let document;
  try {
    [company, document] = await Promise.all([
      fetchCompany(session.token, companyId),
      fetchDocument(session.token, companyId, artifactId),
    ]);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      redirect('/entrar');
    }
    if (error instanceof ApiError && error.status === 404) {
      notFound();
    }
    if (error instanceof ApiError && error.status === 403) {
      return <AccessDenied companyId={companyId} />;
    }
    throw error;
  }

  const canMap = company.permissions.includes('dataset.map');
  const canPublish = company.permissions.includes('dataset.publish');
  const canExport = company.permissions.includes('dataset.export');

  // La vista previa lleva valores del fichero: si este rol no puede mapear, no
  // se pide siquiera. Pedirla y esconder el 403 seria pedir lo que no toca.
  let preview: PreviewPage | null = null;
  let previewError: string | null = null;
  if (canMap) {
    try {
      preview = await fetchPreview(
        session.token,
        companyId,
        artifactId,
        page * pageSize,
        pageSize,
      );
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        redirect('/entrar');
      }
      if (error instanceof ApiError && error.status === 403) {
        return <AccessDenied companyId={companyId} />;
      }
      if (error instanceof ApiError && error.status === 404) {
        notFound();
      }
      if (error instanceof ApiError && error.status === 503) {
        throw error;
      }
      previewError =
        error instanceof ApiError
          ? error.message
          : 'la vista previa no se pudo leer';
    }
  }

  let mappings: MappingSummary[] = [];
  if (canMap) {
    const loaded = await loadAuthorized(
      fetchMappings(session.token, companyId, artifactId),
    );
    if (!loaded.allowed) {
      return <AccessDenied companyId={companyId} />;
    }
    mappings = loaded.value;
  }
  const requestedMappingId = singleQueryValue(query.mapeo);
  const mappingSelection = selectMappingVersion(
    requestedMappingId,
    query.fuente !== undefined,
    mappings.map((item) => item.mapping_version_id),
  );
  const invalidMappingRequested =
    (query.mapeo !== undefined && requestedMappingId === null) ||
    mappingSelection.invalidRequestedId;
  const selectedId = mappingSelection.selectedId;
  let mapping: MappingDetail | null = null;
  if (canMap && selectedId) {
    const loaded = await loadAuthorized(
      fetchMapping(session.token, companyId, selectedId),
    );
    if (!loaded.allowed) {
      return <AccessDenied companyId={companyId} />;
    }
    mapping = loaded.value;
  }

  const loadedDatasets = await loadAuthorized(
    fetchDatasets(session.token, companyId, artifactId),
  );
  if (!loadedDatasets.allowed) {
    return <AccessDenied companyId={companyId} />;
  }
  const datasets = loadedDatasets.value;
  const requestedDatasetId = singleQueryValue(query.dataset);
  const datasetSelection = selectDatasetVersion(
    requestedDatasetId,
    query.dataset !== undefined,
    datasets.map((item) => item.dataset_version_id),
  );
  const selectedDatasetSummary = datasetSelection.selectedId
    ? datasets.find(
        (item) => item.dataset_version_id === datasetSelection.selectedId,
      ) ?? null
    : null;
  let dataset: DatasetDetail | null = null;
  let movements: Movement[] = [];
  let overrides: RowOverrideSummary[] = [];
  let corrections: CorrectionProposal[] = [];
  if (selectedDatasetSummary) {
    const loadedDataset = await loadAuthorized(
      fetchDataset(
        session.token,
        companyId,
        selectedDatasetSummary.dataset_version_id,
      ),
    );
    if (!loadedDataset.allowed) {
      return <AccessDenied companyId={companyId} />;
    }
    dataset = loadedDataset.value;
    const loadedMovements = await loadAuthorized(
      fetchMovements(
        session.token,
        companyId,
        selectedDatasetSummary.dataset_version_id,
        movementPage * movementPageSize,
        movementPageSize + 1,
      ),
    );
    if (!loadedMovements.allowed) {
      return <AccessDenied companyId={companyId} />;
    }
    movements = loadedMovements.value;
    const loadedOverrides = await loadAuthorized(
      fetchOverrides(
        session.token,
        companyId,
        selectedDatasetSummary.dataset_version_id,
      ),
    );
    if (!loadedOverrides.allowed) {
      return <AccessDenied companyId={companyId} />;
    }
    overrides = loadedOverrides.value;
    const loadedCorrections = await loadAuthorized(
      fetchCorrections(
        session.token,
        companyId,
        selectedDatasetSummary.dataset_version_id,
      ),
    );
    if (!loadedCorrections.allowed) {
      return <AccessDenied companyId={companyId} />;
    }
    corrections = loadedCorrections.value;
  }

  // Los maestros salen de la API, no de una constante: una cuenta escrita a
  // mano en la interfaz seria una cuenta que la base no conoce.
  const loadedAccounts = await loadAuthorized(
    fetchAccountsFull(session.token, companyId),
  );
  if (!loadedAccounts.allowed) {
    return <AccessDenied companyId={companyId} />;
  }
  const accountRows = loadedAccounts.value;
  const loadedSources = await loadAuthorized(
    fetchSourcesFull(session.token, companyId),
  );
  if (!loadedSources.allowed) {
    return <AccessDenied companyId={companyId} />;
  }
  const sourceRows: Source[] = loadedSources.value.filter(
    (source) => source.status === 'active',
  );
  const accounts = accountRows
    .filter((account) => account.status === 'active')
    .map((account) => ({
    account_id: account.account_id,
    label:
      `${account.display_name} · ${account.currency_code}` +
      (account.identifier_last4 ? ` · ...${account.identifier_last4}` : ''),
  }));
  const requestedSourceId = singleQueryValue(query.fuente);
  const requestedSource = requestedSourceId
    ? sourceRows.find((source) => source.data_source_id === requestedSourceId) ?? null
    : null;
  const invalidSourceRequested =
    query.fuente !== undefined &&
    (requestedSourceId === null || requestedSource === null);
  const mappingSourceConflict =
    mapping !== null &&
    requestedSource !== null &&
    mapping.data_source_id !== requestedSource.data_source_id;
  const dataSourceId = mapping?.data_source_id ?? requestedSource?.data_source_id ?? '';
  const flowContext = {
    documento: artifactId,
    // Una fuente no autorizada se explica, pero nunca se propaga a enlaces
    // nuevos como si hubiera pasado la validacion.
    fuente: dataSourceId || null,
    mapeo: selectedId,
    dataset: datasetSelection.selectedId,
    pagina: page,
    movimientosPagina: movementPage,
  };

  return (
    <main>
      <header className="bar">
        <div>
          <h1>{document.filename}</h1>
          <span className="who">
            Original · Extraccion · Mapping · Canonico
          </span>
        </div>
        <nav aria-label="Navegacion del documento">
          <Link
            href={withFlowContext(
              `/empresas/${companyId}/documentos/${artifactId}`,
              flowContext,
            )}
          >
            Ver el perfil
          </Link>{' '}
          <Link href={`/empresas/${companyId}`}>Volver</Link>
        </nav>
      </header>

      {/* ------------------------------------------------------- Original --- */}
      <h2 id="original">Original</h2>
      <section className="card" aria-labelledby="original">
        <div className="meta">
          <strong>{document.zone}</strong> · {document.media_type} ·{' '}
          {document.byte_size.toLocaleString('es-CO')} B
        </div>
        <code className="digest">{document.content_sha256}</code>
        {document.zone === 'quarantine' ? (
          <p className="notice" role="status">
            Este documento sigue en cuarentena, asi que no se ha leido y no hay
            nada que mapear. Lo que no se puede inspeccionar entero se queda
            aqui en vez de pasar por bueno.
          </p>
        ) : (
          <p className="meta">
            La huella es la identidad del documento, y es la que aparece en cada
            coordenada del linaje.
          </p>
        )}
      </section>

      {/* ----------------------------------------------------- Extraccion --- */}
      <h2 id="extraccion">Extraccion</h2>
      {!canMap ? (
        <p className="card">
          Ver el contenido de un fichero pide <code>dataset.map</code>, que es
          mas que ver el documento. El perfil dice como es el fichero; esto dice
          que pone en el.
        </p>
      ) : previewError ? (
        <p className="notice error" role="alert">
          {previewError}
        </p>
      ) : preview === null ? (
        <p className="card">Leyendo el documento...</p>
      ) : preview.total_records === 0 ? (
        <p className="card">El documento no tiene registros.</p>
      ) : (
        <>
          <section className="card" aria-labelledby="extraccion">
            <div className="meta">
              {preview.total_records.toLocaleString('es-CO')} registro(s) ·{' '}
              cabecera en la fila {preview.header_row} · datos desde la fila{' '}
              {preview.first_data_row}
            </div>
            {preview.truncated ? (
              <p className="notice error" role="status">
                La lectura se detuvo antes de acabar:{' '}
                {TRUNCATION_LABELS[preview.truncation_reason ?? ''] ??
                  preview.truncation_reason}
                . Lo que ves no es el fichero entero, y publicarlo asi dejaria
                fuera filas sin decirlo.
              </p>
            ) : null}
          </section>

          <div className="card scroll">
            <table>
              <caption className="meta">
                Cada fila lleva su numero dentro del fichero. Es el mismo numero
                que aparece en el linaje de un importe publicado.
              </caption>
              <thead>
                <tr>
                  <th scope="col">Fila</th>
                  {preview.header.map((header, index) => (
                    <th key={`${header}-${index}`} scope="col">
                      {index + 1}. {header}
                      {preview.columns[index] ? (
                        <span className="meta">
                          {' '}
                          {TYPE_LABELS[preview.columns[index].inferred_type] ??
                            preview.columns[index].inferred_type}{' '}
                          {Math.round(preview.columns[index].type_confidence * 100)}%
                        </span>
                      ) : null}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((row) => (
                  <tr key={row.record_ordinal}>
                    <th scope="row" className="when">
                      {row.record_ordinal}
                      {row.record_ordinal === preview.header_row ? ' (cabecera)' : ''}
                    </th>
                    {row.values.map((value, index) => (
                      <td key={index}>{value}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <nav className="card" aria-label="Paginacion de la vista previa">
            {page > 0 ? (
              <Link
                href={withFlowContext(flowPath, {
                  ...flowContext,
                  pagina: page - 1,
                })}
              >
                Pagina anterior
              </Link>
            ) : (
              <span className="meta">Primera pagina</span>
            )}{' '}
            ·{' '}
            {(page + 1) * pageSize < preview.total_records ? (
              <Link
                href={withFlowContext(flowPath, {
                  ...flowContext,
                  pagina: page + 1,
                })}
              >
                Pagina siguiente
              </Link>
            ) : (
              <span className="meta">Ultima pagina</span>
            )}
          </nav>
        </>
      )}

      {/* -------------------------------------------------------- Mapping --- */}
      <h2 id="mapping">Mapping</h2>
      {!canMap ? (
        <p className="card">Mapear columnas pide <code>dataset.map</code>.</p>
      ) : preview === null ? (
        <p className="card">
          No hay nada extraido todavia, asi que no hay columnas que asignar.
        </p>
      ) : (
        <>
          {invalidSourceRequested ? (
            <p className="notice error" role="alert">
              La fuente indicada en la URL no pertenece a las fuentes que el
              servidor autorizo para esta empresa. Elige una fuente de la lista.
            </p>
          ) : null}
          {invalidMappingRequested ? (
            <p className="notice error" role="alert">
              La version de mapeo indicada no pertenece a este documento o ya no
              esta disponible. No se ha sustituido por otra version en silencio.
            </p>
          ) : null}
          {mappingSourceConflict ? (
            <p className="notice error" role="alert">
              La fuente de la URL y la version de mapeo elegida son distintas.
              Se muestra la fuente historica del mapeo, pero no se sustituyo el
              contexto en silencio. Abre otra version o crea un mapeo nuevo.
            </p>
          ) : null}
          {mappings.length > 0 ? (
            <nav className="card" aria-label="Versiones de mapeo">
              <div className="meta">
                Versiones · hasta 100; el API actual no expone otra pagina
              </div>
              <ul>
                {mappings.map((item) => (
                  <li key={item.mapping_version_id}>
                    <Link
                      href={withFlowContext(flowPath, {
                        ...flowContext,
                        mapeo: item.mapping_version_id,
                      })}
                      aria-current={
                        item.mapping_version_id === selectedId ? 'true' : undefined
                      }
                    >
                      v{item.version_number} · {item.display_name}
                    </Link>{' '}
                    <span className="outcome">
                      {STATE_LABELS[item.state] ?? item.state}
                    </span>
                  </li>
                ))}
              </ul>
            </nav>
          ) : null}

          {mapping && mapping.blockers.length > 0 ? (
            <section className="card" aria-labelledby="bloqueos">
              <h3 id="bloqueos">Que falta por decidir</h3>
              <p className="notice error" role="status">
                No se elige por ti. Leer mal una fecha o un separador de miles
                mueve un asiento y nadie lo nota hasta el cierre.
              </p>
              <ul>
                {mapping.blockers.map((blocker: Blocker, index: number) => (
                  <DecisionForm
                    key={`${blocker.code}-${blocker.subject_ref}-${index}`}
                    companyId={companyId}
                    artifactId={artifactId}
                    mappingVersionId={mapping.mapping_version_id}
                    blocker={blocker}
                  />
                ))}
              </ul>
            </section>
          ) : null}

          {mapping && mapping.unaccounted_columns.length > 0 ? (
            <p className="notice" role="status">
              Estas columnas no se usan y nadie declaro que se ignoran:{' '}
              {mapping.unaccounted_columns
                .map((column) => `${column.index + 1}. ${column.header}`)
                .join(', ')}
              . No bloquea nada. Declararlo deja escrito «la vi y decidi no
              usarla», que es distinto de «se me paso», y la diferencia importa
              cuando quien revisa no es quien mapeo.
            </p>
          ) : null}

          {mapping && mapping.decisions.length > 0 ? (
            <section className="card scroll" aria-label="Decisiones registradas">
              <table>
                <caption className="meta">
                  Lo que alguien eligio, y por que. Cambiar de opinion es una
                  version de mapeo nueva, no una reescritura de esto.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Sobre</th>
                    <th scope="col">Eleccion</th>
                    <th scope="col">Motivo</th>
                    <th scope="col">Cuando</th>
                  </tr>
                </thead>
                <tbody>
                  {mapping.decisions.map((decision) => (
                    <tr key={decision.decision_id}>
                      <td>{decision.subject_ref}</td>
                      <td>{decision.resolved_value}</td>
                      <td>{decision.rationale}</td>
                      <td className="when">{decision.decided_at}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ) : null}

          <section className="card" aria-label="Asignar columnas">
            <h3>Asignar columnas</h3>
            <MappingForm
              key={`${selectedId ?? 'nuevo'}:${dataSourceId}`}
              companyId={companyId}
              artifactId={artifactId}
              sources={sourceRows.map((source) => ({
                data_source_id: source.data_source_id,
                display_name: source.display_name,
                source_family: source.source_family,
                status: source.status,
              }))}
              selectedDataSourceId={dataSourceId}
              page={page}
              movementPage={movementPage}
              preview={preview}
            />
          </section>

          {mapping && mapping.blockers.length === 0 ? (
            <section className="card" aria-label="Preparar el conjunto">
              <h3>Preparar</h3>
              <p className="meta">
                Preparar convierte las filas en movimientos y los deja
                <strong> validados</strong>, no publicados. Publicarlos es de
                otra persona.
              </p>
              <PrepareForm
                companyId={companyId}
                artifactId={artifactId}
                mappingVersionId={mapping.mapping_version_id}
                accounts={accounts}
              />
            </section>
          ) : null}
        </>
      )}

      {/* ------------------------------------------------------- Canonico --- */}
      <h2 id="canonico">Canonico</h2>
      <p className="meta">
        Se consultan hasta 50 versiones del conjunto. La mas reciente se abre
        por defecto; una version elegida permanece en la URL y el API actual no
        expone otra pagina.
      </p>
      {datasets.length > 0 ? (
        <nav className="card version-picker" aria-label="Versiones del conjunto">
          <span className="meta">Historico:</span>
          {datasets.map((item, index) => (
            <Link
              key={item.dataset_version_id}
              aria-current={
                item.dataset_version_id === datasetSelection.selectedId
                  ? 'page'
                  : undefined
              }
              href={withFlowContext(flowPath, {
                ...flowContext,
                dataset: item.dataset_version_id,
                movimientosPagina: 0,
              })}
            >
              {index === 0 ? 'Mas reciente' : item.prepared_at.slice(0, 10)} ·{' '}
              {STATE_LABELS[item.state] ?? item.state}
            </Link>
          ))}
        </nav>
      ) : null}
      {datasetSelection.invalidRequestedId ? (
        <p className="notice error" role="alert">
          La version solicitada no pertenece a este documento o ya no esta
          disponible. Elige una version del historico autorizado.
        </p>
      ) : null}
      {dataset === null ? (
        <p className="card">
          {datasets.length === 0
            ? 'Todavia no hay ningun conjunto canonico para este documento.'
            : 'No hay una version autorizada seleccionada.'}
        </p>
      ) : (
        <>
          <section className="card" aria-labelledby="canonico">
            <div className="meta">
              <strong>{STATE_LABELS[dataset.state] ?? dataset.state}</strong> ·{' '}
              {dataset.movement_count} movimiento(s) de {dataset.record_count}{' '}
              fila(s) · {dataset.rejected_count} rechazada(s) · motor{' '}
              <code>{dataset.engine_release}</code>
            </div>
            {dataset.manifest ? (
              <p className="meta">
                Clave de reproduccion{' '}
                <code className="digest">{dataset.manifest.reproduction_key}</code>
                {' · '}
                {dataset.manifest.locale} · {dataset.manifest.timezone}
              </p>
            ) : null}

            {dataset.publish_blockers.length > 0 && dataset.state === 'validated' ? (
              <div className="notice" role="status">
                <strong>Antes de publicar:</strong>
                <ul>
                  {dataset.publish_blockers.map((blocker) => (
                    <li key={blocker.code}>
                      {PUBLISH_BLOCKER_LABELS[blocker.code] ?? blocker.detail}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            <section aria-labelledby="revision-excepciones">
              <h3 id="revision-excepciones">Revision y excepciones</h3>
              {overrides.length === 0 ? (
                <p className="meta">
                  Esta version no tiene excepciones por fila registradas.
                </p>
              ) : (
                <div className="scroll">
                  <table>
                    <caption className="meta">
                      Solo metadatos de la decision. Los valores y sus huellas no
                      viajan en estos formularios.
                    </caption>
                    <thead>
                      <tr>
                        <th scope="col">Campo</th>
                        <th scope="col">Tipo</th>
                        <th scope="col">Motivo</th>
                        <th scope="col">Autor</th>
                        <th scope="col">Revision</th>
                      </tr>
                    </thead>
                    <tbody>
                      {overrides.map((item) => (
                        <tr key={item.override_id}>
                          <th scope="row">
                            {FIELD_LABELS[item.canonical_field] ?? item.canonical_field}
                          </th>
                          <td>{item.override_kind}</td>
                          <td><code>{item.reason_code}</code></td>
                          <td className="when">
                            <code>{item.created_by.slice(0, 8)}</code>
                          </td>
                          <td>
                            {item.approved ? (
                              <span className="outcome">aprobada</span>
                            ) : item.needs_approval ? (
                              canPublish && dataset.state === 'validated' ? (
                                <OverrideApprovalForm
                                  companyId={companyId}
                                  artifactId={artifactId}
                                  datasetVersionId={dataset.dataset_version_id}
                                  overrideId={item.override_id}
                                />
                              ) : (
                                <span className="notice">pendiente de otro revisor</span>
                              )
                            ) : (
                              <span className="meta">no requiere aprobacion</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <section aria-labelledby="revision-correcciones">
              <h3 id="revision-correcciones">Correcciones propuestas</h3>
              {corrections.length === 0 ? (
                <p className="meta">
                  Esta version no tiene correcciones tipadas propuestas.
                </p>
              ) : (
                <div className="correction-review-list">
                  {corrections.map((item) => (
                    <article className="notice" key={item.overlay_id}>
                      <div>
                        <strong>
                          {CORRECTION_FIELD_LABELS[item.field] ?? item.field}:{' '}
                          propuesta <code>{item.proposed_value}</code>
                        </strong>
                        <span className="outcome">
                          {CORRECTION_STATUS_LABELS[item.status] ?? item.status}
                        </span>
                      </div>
                      <p>
                        {item.reason_comment}{' '}
                        <Link
                          href={withFlowContext(
                            `/empresas/${companyId}/movimientos/${item.movement_id}`,
                            flowContext,
                          )}
                        >
                          Comparar con el valor actual
                        </Link>
                      </p>
                      <p className="meta">
                        Autor: {item.author_name} · secuencia {item.sequence} ·{' '}
                        motivo <code>{item.reason_code}</code>
                      </p>
                      {item.status === 'pending_review' ? (
                        canPublish && dataset.state === 'validated' ? (
                          <CorrectionReviewForm
                            companyId={companyId}
                            artifactId={artifactId}
                            datasetVersionId={dataset.dataset_version_id}
                            overlayId={item.overlay_id}
                          />
                        ) : (
                          <p className="notice">Pendiente de un revisor autorizado.</p>
                        )
                      ) : item.status === 'approved' ? (
                        <p className="notice warning">
                          La aprobacion no altero el dataset base. Falta aplicar en
                          una version nueva antes de publicar.
                        </p>
                      ) : (
                        <p className="meta">
                          Rechazada por {item.reviewer_name}: {item.review_rationale}
                        </p>
                      )}
                    </article>
                  ))}
                </div>
              )}
            </section>

            {canPublish && dataset.state === 'validated' ? (
              <details>
                <summary>Rechazar esta version</summary>
                <RejectDatasetForm
                  companyId={companyId}
                  artifactId={artifactId}
                  datasetVersionId={dataset.dataset_version_id}
                />
              </details>
            ) : null}
            {dataset.state === 'staging' ? (
              <>
                <p className="notice" role="status">
                  Este conjunto esta a medias: {dataset.movement_count} de{' '}
                  {dataset.expected_record_count ?? '?'} fila(s). No es publicable
                  ni aparece como publicado, y lo que ya entro no se repite al
                  continuar.
                </p>
                <ContinueForm
                  companyId={companyId}
                  artifactId={artifactId}
                  datasetVersionId={dataset.dataset_version_id}
                />
              </>
            ) : dataset.state === 'published' ? (
              <>
                <p className="notice ok" role="status">
                  Publicado. Reprocesar creara otra version y esta se conserva: lo
                  publicado no se reescribe.
                </p>
                {isDatasetExportEligible(canExport, dataset) ? (
                  <aside className="export-panel" aria-labelledby="salida-limpia">
                    <div>
                      <h3 id="salida-limpia">Salida limpia</h3>
                      <p>
                        CSV canonico con fechas ISO e importes decimales exactos.
                        Es una exportacion operativa no certificada: no demuestra
                        conciliacion de saldos ni cierre contable.
                      </p>
                    </div>
                    <a
                      className="button-link"
                      download
                      href={
                        `/api/companies/${encodeURIComponent(companyId)}/datasets/` +
                        `${encodeURIComponent(dataset.dataset_version_id)}/export`
                      }
                    >
                      Descargar CSV canonico
                    </a>
                  </aside>
                ) : null}
              </>
            ) : dataset.state === 'rejected' ? (
              <p className="notice error" role="status">
                Version rechazada y conservada solo para consulta.
                {dataset.rejected_reason
                  ? ` Motivo: ${dataset.rejected_reason}`
                  : ''}
              </p>
            ) : (
              <PublishForm
                companyId={companyId}
                artifactId={artifactId}
                datasetVersionId={dataset.dataset_version_id}
                canPublish={dataset.can_publish}
                reason={
                  dataset.publish_blockers.length > 0
                    ? PUBLISH_BLOCKER_LABELS[
                        dataset.publish_blockers[0]?.code ?? ''
                      ] ??
                      dataset.publish_blockers[0]?.detail ??
                      'Esta version tiene una restriccion pendiente.'
                    : `Un conjunto en ${STATE_LABELS[dataset.state] ?? dataset.state} no se publica.`
                }
              />
            )}
          </section>

          {movements.length > 0 ? (
            <>
            <div className="card scroll">
              <table>
                <caption className="meta">
                  El importe es siempre positivo y la direccion lleva el signo.
                  Cada movimiento enlaza con la celda que lo produjo.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Fila</th>
                    <th scope="col">Fecha</th>
                    <th scope="col">Descripcion</th>
                    <th scope="col">Referencia</th>
                    <th scope="col">Direccion</th>
                    <th scope="col">Importe</th>
                  </tr>
                </thead>
                <tbody>
                  {movements.slice(0, movementPageSize).map((movement) => (
                    <tr key={movement.movement_id}>
                      <th scope="row" className="when">
                        <Link
                          href={withFlowContext(
                            `/empresas/${companyId}/movimientos/${movement.movement_id}`,
                            flowContext,
                          )}
                        >
                          {movement.record_ordinal}
                        </Link>
                      </th>
                      <td className="when">{movement.occurred_on}</td>
                      <td>{movement.description}</td>
                      <td>{movement.reference ?? '—'}</td>
                      <td>
                        <span className="outcome">
                          {movement.direction === 'inflow' ? 'entrada' : 'salida'}
                        </span>
                      </td>
                      <td className="when">
                        {money(movement.amount, movement.currency)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <nav className="card bar" aria-label="Paginas de movimientos">
              {movementPage > 0 ? (
                <Link
                  href={withFlowContext(flowPath, {
                    ...flowContext,
                    movimientosPagina: movementPage - 1,
                  })}
                >
                  Movimientos anteriores
                </Link>
              ) : (
                <span className="meta">Primera pagina de movimientos</span>
              )}
              {movements.length > movementPageSize ? (
                <Link
                  href={withFlowContext(flowPath, {
                    ...flowContext,
                    movimientosPagina: movementPage + 1,
                  })}
                >
                  Movimientos siguientes
                </Link>
              ) : (
                <span className="meta">Ultima pagina de movimientos</span>
              )}
            </nav>
            </>
          ) : (
            <p className="card">Este conjunto no tiene movimientos en esta pagina.</p>
          )}
        </>
      )}
    </main>
  );
}

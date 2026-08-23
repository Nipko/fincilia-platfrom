import Link from 'next/link';
import { redirect } from 'next/navigation';

import {
  ApiError,
  fetchAccounts,
  fetchCompany,
  fetchDataset,
  fetchDatasets,
  fetchDocument,
  fetchMapping,
  fetchMappings,
  fetchMovements,
  fetchPreview,
  fetchSources,
  type Blocker,
  type DatasetDetail,
  type MappingDetail,
  type Movement,
  type PreviewPage,
} from '@/lib/api';
import { readSession } from '@/lib/session';

import {
  DecisionForm,
  MappingForm,
  PrepareForm,
  PublishForm,
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
  validated: 'validado',
  published: 'publicado',
  rejected: 'rechazado',
  superseded: 'sustituido',
};

const TRUNCATION_LABELS: Record<string, string> = {
  row_limit: 'se alcanzo el limite de filas',
  byte_limit: 'se alcanzo el limite de bytes',
  time_limit: 'se alcanzo el limite de tiempo',
};

function money(amount: string, currency: string): string {
  // Punto fijo, sin `Number`: convertir a coma flotante para ensenar un importe
  // es perderlo en el unico sitio donde no se puede perder.
  const [whole = '0', fraction = ''] = amount.split('.');
  const trimmed = fraction.replace(/0+$/, '');
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return `${grouped}${trimmed ? `,${trimmed}` : ''} ${currency}`;
}

export default async function MappingPage({
  params,
  searchParams,
}: {
  params: Promise<{ companyId: string; artifactId: string }>;
  searchParams: Promise<{ pagina?: string; mapeo?: string }>;
}) {
  const session = await readSession();
  if (!session) {
    redirect('/entrar');
  }
  const { companyId, artifactId } = await params;
  const query = await searchParams;
  const page = Math.max(0, Number.parseInt(query.pagina ?? '0', 10) || 0);
  const pageSize = 25;

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
    return (
      <main>
        <header className="bar">
          <h1>Sin acceso</h1>
          <Link href={`/empresas/${companyId}`}>Volver</Link>
        </header>
        <p className="card">
          Esta cuenta no tiene acceso vigente a lo que has pedido.
        </p>
      </main>
    );
  }

  const canMap = company.permissions.includes('dataset.map');
  const canPublish = company.permissions.includes('dataset.publish');

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
      previewError =
        error instanceof ApiError
          ? error.message
          : 'la vista previa no se pudo leer';
    }
  }

  const mappings = canMap
    ? await fetchMappings(session.token, companyId, artifactId).catch(() => [])
    : [];
  const selectedId = query.mapeo ?? mappings[0]?.mapping_version_id ?? null;
  let mapping: MappingDetail | null = null;
  if (canMap && selectedId) {
    mapping = await fetchMapping(session.token, companyId, selectedId).catch(
      () => null,
    );
  }

  const datasets = await fetchDatasets(session.token, companyId, artifactId).catch(
    () => [],
  );
  const latest = datasets[0] ?? null;
  let dataset: DatasetDetail | null = null;
  let movements: Movement[] = [];
  if (latest) {
    dataset = await fetchDataset(
      session.token,
      companyId,
      latest.dataset_version_id,
    ).catch(() => null);
    movements = await fetchMovements(
      session.token,
      companyId,
      latest.dataset_version_id,
      0,
      50,
    ).catch(() => []);
  }

  // Los maestros salen de la API, no de una constante: una cuenta escrita a
  // mano en la interfaz seria una cuenta que la base no conoce.
  const [accountRows, sourceRows] = await Promise.all([
    fetchAccounts(session.token, companyId).catch(() => []),
    fetchSources(session.token, companyId).catch(() => []),
  ]);
  const accounts = accountRows.map((account) => ({
    account_id: account.account_id,
    label:
      `${account.display_name} · ${account.currency_code}` +
      (account.identifier_last4 ? ` · ...${account.identifier_last4}` : ''),
  }));
  const dataSourceId =
    mapping?.data_source_id ?? sourceRows[0]?.data_source_id ?? '';

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
          <Link href={`/empresas/${companyId}/documentos/${artifactId}`}>
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
                href={`/empresas/${companyId}/documentos/${artifactId}/mapeo?pagina=${page - 1}`}
              >
                Pagina anterior
              </Link>
            ) : (
              <span className="meta">Primera pagina</span>
            )}{' '}
            ·{' '}
            {(page + 1) * pageSize < preview.total_records ? (
              <Link
                href={`/empresas/${companyId}/documentos/${artifactId}/mapeo?pagina=${page + 1}`}
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
          {mappings.length > 0 ? (
            <nav className="card" aria-label="Versiones de mapeo">
              <div className="meta">Versiones</div>
              <ul>
                {mappings.map((item) => (
                  <li key={item.mapping_version_id}>
                    <Link
                      href={`/empresas/${companyId}/documentos/${artifactId}/mapeo?mapeo=${item.mapping_version_id}`}
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
              companyId={companyId}
              artifactId={artifactId}
              dataSourceId={dataSourceId}
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
      {dataset === null ? (
        <p className="card">
          Todavia no hay ningun conjunto canonico para este documento.
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
            {dataset.state === 'published' ? (
              <p className="notice ok" role="status">
                Publicado. Reprocesar creara otra version y esta se conserva: lo
                publicado no se reescribe.
              </p>
            ) : (
              <PublishForm
                companyId={companyId}
                artifactId={artifactId}
                datasetVersionId={dataset.dataset_version_id}
                canPublish={dataset.can_publish}
                reason={
                  !canPublish
                    ? 'Publicar pide dataset.publish, que no esta en este rol.'
                    : dataset.state !== 'validated'
                      ? `Un conjunto en ${STATE_LABELS[dataset.state] ?? dataset.state} no se publica.`
                      : 'Quien preparo esta version no puede publicarla. Tiene que revisarla otra persona.'
                }
              />
            )}
          </section>

          {movements.length > 0 ? (
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
                  {movements.map((movement) => (
                    <tr key={movement.movement_id}>
                      <th scope="row" className="when">
                        <Link
                          href={`/empresas/${companyId}/movimientos/${movement.movement_id}`}
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
          ) : null}
        </>
      )}
    </main>
  );
}

import Link from 'next/link';
import { notFound, redirect } from 'next/navigation';

import {
  ApiError,
  fetchDocument,
  fetchSource,
  type SourceDetail,
  type TableProfile,
} from '@/lib/api';
import {
  pageFromQuery,
  singleQueryValue,
  withFlowContext,
} from '@/lib/navigation';
import { readSession } from '@/lib/session';
import { isUuid } from '@/lib/upload-policy';

export const dynamic = 'force-dynamic';

const PROMOTION_REASONS: Record<string, string> = {
  content_inspected: 'contenido inspeccionado por completo',
  sensitive_content: 'se detecto informacion sensible',
  no_scanner_for_format: 'todavia no hay analizador seguro para este formato',
  macro_enabled_archive: 'el libro contiene macros',
  unscannable: 'no se pudo examinar',
};

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

function asProfile(value: unknown): TableProfile | null {
  if (!value || typeof value !== 'object' || !('columns' in value)) {
    return null;
  }
  return value as TableProfile;
}

export default async function DocumentPage({
  params,
  searchParams,
}: {
  params: Promise<{ companyId: string; artifactId: string }>;
  searchParams: Promise<{
    fuente?: string | string[];
    mapeo?: string | string[];
    pagina?: string | string[];
    movimientosPagina?: string | string[];
  }>;
}) {
  const session = await readSession();
  if (!session) {
    redirect('/entrar');
  }
  const [{ companyId, artifactId }, query] = await Promise.all([params, searchParams]);

  let document;
  try {
    document = await fetchDocument(session.token, companyId, artifactId);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      redirect('/entrar');
    }
    if (error instanceof ApiError && error.status === 404) {
      notFound();
    }
    if (error instanceof ApiError && error.status === 403) {
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
    throw error;
  }

  const requestedSource = singleQueryValue(query.fuente);
  let source: SourceDetail | null = null;
  if (isUuid(requestedSource)) {
    try {
      const candidate = await fetchSource(session.token, companyId, requestedSource);
      source = candidate.status === 'active' ? candidate : null;
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        redirect('/entrar');
      }
      if (!(error instanceof ApiError) || ![403, 404].includes(error.status)) {
        throw error;
      }
      // Un contexto retirado o ajeno se descarta sin revelar cual de los dos era.
    }
  }
  const requestedMapping = singleQueryValue(query.mapeo);
  const flowContext = {
    documento: artifactId,
    fuente: source?.data_source_id ?? null,
    // La version se vuelve a autorizar en MappingPage; aqui solo se conserva
    // si al menos tiene la forma de un identificador, nunca se consulta con ella.
    mapeo: isUuid(requestedMapping) ? requestedMapping : null,
    pagina: pageFromQuery(query.pagina),
    movimientosPagina: pageFromQuery(query.movimientosPagina),
  };

  const run = document.runs.find((item) => item.kind === 'profile');
  const profile = run?.status === 'succeeded' ? asProfile(run.result) : null;

  return (
    <main>
      <header className="bar">
        <div>
          <h1>{document.filename}</h1>
          <span className="who">
            {document.media_type} · {document.byte_size.toLocaleString('es-CO')} B ·{' '}
            {document.zone}
          </span>
        </div>
        <nav aria-label="Navegacion del documento">
          <Link
            href={withFlowContext(
              `/empresas/${companyId}/documentos/${artifactId}/mapeo`,
              flowContext,
            )}
          >
            Mapear y publicar
          </Link>{' '}
          <Link href={withFlowContext(`/empresas/${companyId}`, flowContext)}>
            Volver
          </Link>
        </nav>
      </header>

      {source ? (
        <p className="notice" role="status">
          Fuente seleccionada: <strong>{source.display_name}</strong>. Se volvera a
          validar antes de guardar el mapeo.
        </p>
      ) : null}

      <section className="card">
        <div className="meta">Huella del contenido</div>
        <code className="digest">{document.content_sha256}</code>
        <p className="meta">
          La huella es la identidad del documento. Subir los mismos bytes otra vez
          es la misma entrega, no una nueva.
        </p>
      </section>

      <h2>Zona y decision</h2>
      <div className="card">
        <div className="meta">
          {document.promotion ? (
            <>
              <strong>{document.zone}</strong> ·{' '}
              {PROMOTION_REASONS[document.promotion.reason_code] ??
                document.promotion.reason_code}{' '}
              · escaner {document.promotion.scanner_release}
            </>
          ) : (
            <>
              <strong>{document.zone}</strong> · pendiente de revision
            </>
          )}
        </div>
        {document.zone === 'quarantine' ? (
          <p className="meta">
            La evidencia se conserva. Nada sale de cuarentena sin que su contenido
            se haya inspeccionado entero, y lo que no se puede inspeccionar todavia
            se queda aqui en vez de pasar por bueno.
          </p>
        ) : (
          <p className="meta">
            Se inspecciono el contenido entero antes de promoverlo. El original
            sigue en cuarentena: promover copia, no mueve.
          </p>
        )}
      </div>

      {document.findings.length > 0 ||
      (document.promotion?.findings?.length ?? 0) > 0 ? (
        <>
          <h2>Que se encontro</h2>
          <div className="card">
            <ul>
              {[...document.findings, ...(document.promotion?.findings ?? [])].map(
                (finding, index) => (
                  <li key={`${finding.kind}-${index}`}>
                    <strong>{finding.kind}</strong> · {finding.location} ·{' '}
                    {finding.detail}
                  </li>
                ),
              )}
            </ul>
            <p className="meta">
              El hallazgo dice que tipo y donde, nunca el valor. El fichero se
              conserva; no se promueve ni se procesa.
            </p>
          </div>
        </>
      ) : null}

      <h2>Perfil</h2>
      {!run ? (
        <p className="card">
          Este documento no tiene perfilado, y no lo tendra mientras siga en
          cuarentena: perfilar es leer el fichero entero, y eso no se hace sobre
          algo que no ha pasado inspeccion.
        </p>
      ) : run.status !== 'succeeded' ? (
        <p className="card">
          Perfilado <strong>{run.status}</strong>
          {run.error_code ? ` · ${run.error_code}` : ' · todavia en cola'}.
        </p>
      ) : profile === null ? (
        <p className="card">El perfil no se pudo leer.</p>
      ) : (
        <>
          <div className="card">
            <div className="meta">
              {profile.row_count.toLocaleString('es-CO')} filas ·{' '}
              {profile.column_count} columnas · separador{' '}
              <code>{profile.delimiter || 'ninguno'}</code> · {profile.encoding}
              {profile.has_header ? ' · con cabecera' : ' · sin cabecera'}
              {profile.ragged_rows > 0
                ? ` · ${profile.ragged_rows} filas irregulares`
                : ''}
              {profile.truncated ? ' · truncado' : ''}
            </div>
            {profile.needs_decision.length > 0 ? (
              <p className="notice error" role="status">
                Hay {profile.needs_decision.length} columna(s) que alguien tiene que
                resolver antes de mapear: {profile.needs_decision.join(', ')}. No se
                elige por ti: leer mal una fecha o un separador de miles mueve un
                asiento y nadie lo nota hasta el cierre.
              </p>
            ) : null}
          </div>

          <div className="card scroll">
            <table>
              <caption className="meta">
                Forma detectada de cada columna; no muestra valores del documento.
              </caption>
              <thead>
                <tr>
                  <th scope="col">Columna</th>
                  <th scope="col">Tipo</th>
                  <th scope="col">Confianza</th>
                  <th scope="col">Con valor</th>
                  <th scope="col">Vacias</th>
                  <th scope="col">Longitud</th>
                </tr>
              </thead>
              <tbody>
                {profile.columns.map((column) => (
                  <tr key={column.index}>
                    <th scope="row">{column.header}</th>
                    <td>
                      <span className={`outcome ${column.ambiguous ? 'denied' : ''}`}>
                        {TYPE_LABELS[column.inferred_type] ?? column.inferred_type}
                      </span>
                    </td>
                    <td className="when">
                      {Math.round(column.type_confidence * 100)}%
                    </td>
                    <td className="when">{column.non_empty}</td>
                    <td className="when">{column.empty}</td>
                    <td className="when">
                      {column.min_length}-{column.max_length}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="meta">
              El perfil describe la forma del fichero, no su contenido: cuenta y
              mide, nunca transcribe.
            </p>
          </div>
        </>
      )}
    </main>
  );
}

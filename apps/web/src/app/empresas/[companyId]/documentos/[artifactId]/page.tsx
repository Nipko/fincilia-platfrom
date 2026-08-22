import Link from 'next/link';
import { redirect } from 'next/navigation';

import { ApiError, fetchDocument, type TableProfile } from '@/lib/api';
import { readSession } from '@/lib/session';

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

function asProfile(value: unknown): TableProfile | null {
  if (!value || typeof value !== 'object' || !('columns' in value)) {
    return null;
  }
  return value as TableProfile;
}

export default async function DocumentPage({
  params,
}: {
  params: Promise<{ companyId: string; artifactId: string }>;
}) {
  const session = await readSession();
  if (!session) {
    redirect('/entrar');
  }
  const { companyId, artifactId } = await params;

  let document;
  try {
    document = await fetchDocument(session.token, companyId, artifactId);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      redirect('/entrar');
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
        <Link href={`/empresas/${companyId}`}>Volver</Link>
      </header>

      <section className="card">
        <div className="meta">Huella del contenido</div>
        <code className="digest">{document.content_sha256}</code>
        <p className="meta">
          La huella es la identidad del documento. Subir los mismos bytes otra vez
          es la misma entrega, no una nueva.
        </p>
      </section>

      {document.findings.length > 0 ? (
        <>
          <h2>Por que quedo en cuarentena</h2>
          <div className="card">
            <ul>
              {document.findings.map((finding, index) => (
                <li key={`${finding.kind}-${index}`}>
                  <strong>{finding.kind}</strong> · {finding.location} ·{' '}
                  {finding.detail}
                </li>
              ))}
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
          Este documento no tiene perfilado. Solo se perfila lo que sale de
          cuarentena.
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
              <thead>
                <tr>
                  <th>Columna</th>
                  <th>Tipo</th>
                  <th>Confianza</th>
                  <th>Con valor</th>
                  <th>Vacias</th>
                  <th>Longitud</th>
                </tr>
              </thead>
              <tbody>
                {profile.columns.map((column) => (
                  <tr key={column.index}>
                    <td>{column.header}</td>
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

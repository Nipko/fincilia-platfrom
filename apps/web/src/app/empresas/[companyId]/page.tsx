import Link from 'next/link';
import { notFound, redirect } from 'next/navigation';

import {
  ApiError,
  fetchAudit,
  fetchCompany,
  fetchDatasets,
  fetchDocuments,
  fetchExpectations,
  fetchSourcesFull,
  type ArtifactSummary,
  type AuditEvent,
  type DatasetSummary,
  type Expectation,
  type Source,
} from '@/lib/api';
import { summarizeDatasets, summarizeExpectations } from '@/lib/portfolio';
import { readSession } from '@/lib/session';
import { UploadForm } from './upload';

export const dynamic = 'force-dynamic';

const PROMOTION_REASONS: Record<string, string> = {
  content_inspected: 'contenido inspeccionado por completo',
  sensitive_content: 'se detecto informacion sensible',
  no_scanner_for_format: 'todavia no hay analizador seguro para este formato',
  macro_enabled_archive: 'el libro contiene macros',
  active_workbook_content: 'el libro contiene objetos activos o enlaces externos',
  formula_review_required: 'el libro contiene formulas y requiere revision explicita',
  worksheet_selection_required: 'el libro requiere elegir una hoja de forma explicita',
  unsafe_or_malformed_workbook: 'el libro esta danado o usa una estructura no segura',
  unscannable: 'no se pudo examinar',
};

function formatWhen(value: string): string {
  // Sin libreria de fechas: el ISO ya viene del servidor y recortarlo no
  // reinterpreta nada. Una libreria de zonas horarias aqui solo anadiria una
  // forma nueva de mostrar una hora que no es la del hecho.
  return value.replace('T', ' ').slice(0, 19);
}

export default async function CompanyPage({
  params,
  searchParams,
}: {
  params: Promise<{ companyId: string }>;
  searchParams: Promise<{ fuente?: string | string[] }>;
}) {
  const session = await readSession();
  if (!session) {
    redirect('/entrar');
  }
  const [{ companyId }, query] = await Promise.all([params, searchParams]);

  let company;
  try {
    company = await fetchCompany(session.token, companyId);
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
            <Link href="/empresas">Volver</Link>
          </header>
          <p className="card">
            Esta cuenta no tiene acceso vigente a lo que has pedido. Si crees que
            deberia tenerlo, pidelo a quien administra la empresa.
          </p>
        </main>
      );
    }
    throw error;
  }

  let documents: ArtifactSummary[] = [];
  let documentsVisible = company.permissions.includes('document.read');
  if (company.permissions.includes('document.read')) {
    try {
      documents = await fetchDocuments(session.token, companyId);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        redirect('/entrar');
      }
      if (error instanceof ApiError && error.status === 403) {
        documentsVisible = false;
      } else {
        throw error;
      }
    }
  }

  let uploadSources: Source[] = [];
  let uploadSourcesVisible = company.permissions.includes('document.upload');
  if (uploadSourcesVisible) {
    try {
      uploadSources = (await fetchSourcesFull(session.token, companyId)).filter(
        (source) => source.status === 'active',
      );
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        redirect('/entrar');
      }
      if (error instanceof ApiError && error.status === 403) {
        uploadSourcesVisible = false;
      } else {
        throw error;
      }
    }
  }
  const requestedSource = typeof query.fuente === 'string' ? query.fuente : '';
  const initialSourceId = uploadSources.some(
    (source) => source.data_source_id === requestedSource,
  )
    ? requestedSource
    : '';

  let datasets: DatasetSummary[] | null = null;
  if (company.permissions.includes('movement.read')) {
    try {
      datasets = await fetchDatasets(session.token, companyId);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        redirect('/entrar');
      }
      if (!(error instanceof ApiError) || error.status !== 403) {
        throw error;
      }
    }
  }

  let expectations: Expectation[] | null = null;
  if (company.permissions.includes('document.read')) {
    try {
      expectations = await fetchExpectations(session.token, companyId);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        redirect('/entrar');
      }
      if (!(error instanceof ApiError) || error.status !== 403) {
        throw error;
      }
    }
  }

  const datasetMetric = datasets === null ? null : summarizeDatasets(datasets).value;
  const expectationMetric =
    expectations === null
      ? null
      : summarizeExpectations(
          expectations,
          new Date().toISOString().slice(0, 10),
        ).value;

  // La web no decide: pregunta al servidor si el permiso esta, y si no esta, no
  // pide la auditoria. El servidor volveria a denegarla de todas formas.
  let audit: AuditEvent[] = [];
  let auditVisible = company.permissions.includes('audit.read');
  if (auditVisible) {
    try {
      audit = await fetchAudit(session.token, companyId);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        redirect('/entrar');
      }
      if (!(error instanceof ApiError) || error.status !== 403) {
        throw error;
      }
      auditVisible = false;
    }
  }

  return (
    <main>
      <header className="bar">
        <div>
          <h1>{company.legal_name}</h1>
          <span className="who">
            {company.country_code} · {company.status} · autorizacion v
            {company.authorization_version}
          </span>
        </div>
        <nav aria-label="Navegacion de la empresa">
          {company.permissions.includes('report.read') ? (
            <><Link href={`/informes?empresa=${companyId}`}>Informes</Link>{' '}
              <Link href={`/preparacion-cierre?empresa=${companyId}`}>
                Preparacion de cierre
              </Link>{' '}</>
          ) : null}
          {company.permissions.includes('quality.read') ? (
            <><Link href={`/calidad?empresa=${companyId}`}>Calidad</Link>{' '}</>
          ) : null}
          {company.permissions.includes('member.manage') ? (
            <><Link href={`/empresas/${companyId}/equipo`}>Equipo y roles</Link>{' '}</>
          ) : null}
          {company.permissions.includes('movement.read') ? (
            <><Link href={`/empresas/${companyId}/saldos`}>Saldos</Link>{' '}
              <Link href={`/empresas/${companyId}/conciliacion-saldos`}>Conciliar saldos</Link>{' '}
              <Link href={`/empresas/${companyId}/conciliacion`}>Cruzar movimientos</Link>{' '}</>
          ) : null}
          <Link href={`/empresas/${companyId}/fuentes`}>Fuentes y cuentas</Link>{' '}
          <Link href="/empresas">Empresas</Link>
        </nav>
      </header>

      <section className="card">
        <div className="meta">Roles en esta empresa</div>
        <div className="tags">
          {company.roles.map((role) => (
            <span className="tag" key={role}>
              {role}
            </span>
          ))}
        </div>
        <div className="meta" style={{ marginTop: '1rem' }}>
          Permisos que concede el servidor
        </div>
        <div className="tags">
          {company.permissions.map((permission) => (
            <span className="tag" key={permission}>
              {permission}
            </span>
          ))}
        </div>
      </section>

      <h2>Carga operativa</h2>
      <section className="card" aria-label="Carga operativa de la empresa">
        <p className="meta">
          Conteos de actividad y vencimiento; no son saldos ni una conciliacion.
        </p>
        <dl className="metric-grid">
          <div>
            <dt>Documentos visibles</dt>
            <dd>{documentsVisible ? documents.length : 'Sin acceso para este rol'}</dd>
          </div>
          <div>
            <dt>Por revisar</dt>
            <dd>
              {datasetMetric
                ? `${datasetMetric.pendingReview} version(es) validada(s)`
                : 'Sin acceso para este rol'}
            </dd>
          </div>
          <div>
            <dt>Preparaciones parciales</dt>
            <dd>
              {datasetMetric
                ? `${datasetMetric.partial} version(es)`
                : 'Sin acceso para este rol'}
            </dd>
          </div>
          <div>
            <dt>Ciclos vencidos</dt>
            <dd>
              {expectationMetric
                ? `${expectationMetric.overdue} vencido(s) · ${expectationMetric.dueSoon} proximo(s)`
                : 'Sin acceso para este rol'}
            </dd>
          </div>
        </dl>
      </section>

      <h2>Documentos</h2>
      {uploadSourcesVisible ? (
        <div className="card">
          <UploadForm
            companyId={companyId}
            sources={uploadSources}
            initialSourceId={initialSourceId}
          />
          <p className="meta">
            CSV, PDF o libro de calculo, hasta 25 MB. El tipo se decide por los
            primeros bytes, no por la extension.
          </p>
          <p className="meta">
            Todo lo que se sube entra en <strong>cuarentena</strong>. Sale de ahi
            cuando su contenido se ha inspeccionado entero y no aparece nada
            sensible. Hoy se sabe hacer con CSV y con XLSX sin formulas ni
            contenido activo; si tiene varias hojas, eliges una de forma
            explicita antes de perfilar o extraer. Los demas formatos se quedan
            en cuarentena, y se dice por que.
          </p>
        </div>
      ) : null}

      {!documentsVisible ? (
        <p className="card">
          Este rol no puede consultar documentos. No se presenta como una lista
          vacia porque la ausencia de acceso no dice si existen o no.
        </p>
      ) : documents.length === 0 ? (
        <p className="card">Todavia no hay documentos en esta empresa.</p>
      ) : (
        <div className="card scroll">
          <table>
            <caption className="meta">
              Ultimos 50 documentos. El API actual no expone una pagina siguiente.
            </caption>
            <thead>
              <tr>
                <th scope="col">Fichero</th>
                <th scope="col">Tipo</th>
                <th scope="col">Tamano</th>
                <th scope="col">Zona</th>
                <th scope="col">Huella</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((document) => (
                <tr key={document.artifact_id}>
                  <th scope="row">
                    <Link
                      href={`/empresas/${companyId}/documentos/${document.artifact_id}`}
                    >
                      {document.filename}
                    </Link>
                  </th>
                  <td className="outcome">{document.media_type}</td>
                  <td className="when">{document.byte_size.toLocaleString('es-CO')} B</td>
                  <td>
                    <span
                      className={`outcome ${document.zone === 'quarantine' ? 'denied' : ''}`}
                    >
                      {document.zone}
                    </span>
                    <div className="meta">
                      {document.promotion
                        ? (PROMOTION_REASONS[document.promotion.reason_code] ??
                           document.promotion.reason_code)
                        : 'pendiente de revision'}
                    </div>
                  </td>
                  <td className="when">{document.content_sha256.slice(0, 12)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2>Registro de auditoria</h2>
      {auditVisible ? (
        <p><Link href={`/auditoria?empresa=${encodeURIComponent(companyId)}`}>
          Abrir historial completo con filtros
        </Link></p>
      ) : null}
      {auditVisible ? (
        <div className="card scroll">
          <table>
            <caption className="meta">
              Ultimos 25 eventos. El API actual no expone una pagina siguiente.
            </caption>
            <thead>
              <tr>
                <th scope="col">Cuando</th>
                <th scope="col">Accion</th>
                <th scope="col">Recurso</th>
                <th scope="col">Resultado</th>
              </tr>
            </thead>
            <tbody>
              {audit.map((event) => (
                <tr key={event.audit_event_id}>
                  <th scope="row" className="when">{formatWhen(event.occurred_at)}</th>
                  <td>{event.action}</td>
                  <td>{event.resource_kind}</td>
                  <td>
                    <span className={`outcome ${event.outcome}`}>{event.outcome}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {audit.length === 0 ? <p className="meta">Todavia no hay eventos.</p> : null}
        </div>
      ) : (
        <p className="card">
          Este rol no incluye <code>audit.read</code>, asi que el registro no se
          muestra. No es que este vacio: no corresponde a esta cuenta.
        </p>
      )}
    </main>
  );
}

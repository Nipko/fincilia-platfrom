import Link from 'next/link';
import { redirect } from 'next/navigation';

import {
  ApiError,
  fetchAudit,
  fetchCompany,
  fetchDocuments,
  type ArtifactSummary,
  type AuditEvent,
} from '@/lib/api';
import { readSession } from '@/lib/session';
import { UploadForm } from './upload';

export const dynamic = 'force-dynamic';

function formatWhen(value: string): string {
  // Sin libreria de fechas: el ISO ya viene del servidor y recortarlo no
  // reinterpreta nada. Una libreria de zonas horarias aqui solo anadiria una
  // forma nueva de mostrar una hora que no es la del hecho.
  return value.replace('T', ' ').slice(0, 19);
}

export default async function CompanyPage({
  params,
}: {
  params: Promise<{ companyId: string }>;
}) {
  const session = await readSession();
  if (!session) {
    redirect('/entrar');
  }
  const { companyId } = await params;

  let company;
  try {
    company = await fetchCompany(session.token, companyId);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      redirect('/entrar');
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
  if (company.permissions.includes('document.read')) {
    documents = await fetchDocuments(session.token, companyId);
  }

  // La web no decide: pregunta al servidor si el permiso esta, y si no esta, no
  // pide la auditoria. El servidor volveria a denegarla de todas formas.
  let audit: AuditEvent[] = [];
  let auditVisible = company.permissions.includes('audit.read');
  if (auditVisible) {
    try {
      audit = await fetchAudit(session.token, companyId);
    } catch (error) {
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
        <Link href="/empresas">Volver</Link>
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

      <h2>Documentos</h2>
      {company.permissions.includes('document.upload') ? (
        <div className="card">
          <UploadForm companyId={companyId} />
          <p className="meta">
            CSV, PDF o libro de calculo, hasta 25 MB. El tipo se decide por los
            primeros bytes, no por la extension, y un fichero con datos sensibles se
            queda en cuarentena en vez de pasar a la zona de evidencia.
          </p>
        </div>
      ) : null}

      {documents.length === 0 ? (
        <p className="card">Todavia no hay documentos en esta empresa.</p>
      ) : (
        <div className="card scroll">
          <table>
            <thead>
              <tr>
                <th>Fichero</th>
                <th>Tipo</th>
                <th>Tamano</th>
                <th>Zona</th>
                <th>Huella</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((document) => (
                <tr key={document.artifact_id}>
                  <td>
                    <Link
                      href={`/empresas/${companyId}/documentos/${document.artifact_id}`}
                    >
                      {document.filename}
                    </Link>
                  </td>
                  <td className="outcome">{document.media_type}</td>
                  <td className="when">{document.byte_size.toLocaleString('es-CO')} B</td>
                  <td>
                    <span
                      className={`outcome ${document.zone === 'quarantine' ? 'denied' : ''}`}
                    >
                      {document.zone}
                    </span>
                    {document.findings.length > 0 ? (
                      <div className="meta">
                        {document.findings.map((finding) => finding.kind).join(', ')}
                      </div>
                    ) : null}
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
        <div className="card scroll">
          <table>
            <thead>
              <tr>
                <th>Cuando</th>
                <th>Accion</th>
                <th>Recurso</th>
                <th>Resultado</th>
              </tr>
            </thead>
            <tbody>
              {audit.map((event) => (
                <tr key={event.audit_event_id}>
                  <td className="when">{formatWhen(event.occurred_at)}</td>
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

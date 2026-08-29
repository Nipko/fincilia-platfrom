import Link from 'next/link';
import { notFound, redirect } from 'next/navigation';

import {
  ApiError,
  fetchAccountBalances,
  fetchAccountsFull,
  fetchBalanceReconciliation,
  fetchCloseReadiness,
  fetchCompany,
  fetchDatasets,
  fetchDocuments,
  fetchSourcesFull,
} from '@/lib/api';
import {
  deriveAccountingFlow,
  type AccountingFacts,
  type FlowMetric,
} from '@/lib/accounting-flow';
import { readSession } from '@/lib/session';

export const dynamic = 'force-dynamic';

const STATUS_LABELS = {
  done: 'Con evidencia',
  ready: 'Listo para continuar',
  attention: 'Requiere atención',
  blocked: 'Aún no disponible',
  restricted: 'Sin acceso para este rol',
  unavailable: 'Temporalmente no disponible',
} as const;

async function metric<T>(allowed: boolean, operation: () => Promise<T>): Promise<FlowMetric<T>> {
  if (!allowed) return { state: 'restricted' };
  try {
    return { state: 'available', value: await operation() };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    if (error instanceof ApiError && error.status === 403) return { state: 'restricted' };
    return { state: 'unavailable' };
  }
}

export default async function AccountingFlowPage({
  params,
}: {
  params: Promise<{ companyId: string }>;
}) {
  const session = await readSession();
  if (!session) redirect('/entrar');
  const { companyId } = await params;

  let company;
  try {
    company = await fetchCompany(session.token, companyId);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    if (error instanceof ApiError && error.status === 404) notFound();
    if (error instanceof ApiError && error.status === 403) {
      return (
        <main className="page-state page-state--denied">
          <p className="page-state__label">Acceso restringido</p>
          <h1>Flujo contable no disponible</h1>
          <p className="page-state__description">Esta cuenta no tiene acceso vigente a la empresa solicitada.</p>
          <p className="page-state__action"><Link href="/empresas">Volver al portafolio</Link></p>
        </main>
      );
    }
    throw error;
  }

  const canReadDocuments = company.permissions.includes('document.read');
  const canReadMovements = company.permissions.includes('movement.read');
  const canReadReports = company.permissions.includes('report.read');

  const [accountsResult, sourcesResult, documentsResult, datasetsResult,
    balanceResult, reconciliationResult, closeResult] = await Promise.all([
    metric(canReadMovements, () => fetchAccountsFull(session.token, companyId)),
    metric(canReadDocuments, () => fetchSourcesFull(session.token, companyId)),
    metric(canReadDocuments, () => fetchDocuments(session.token, companyId)),
    metric(canReadMovements, () => fetchDatasets(session.token, companyId)),
    metric(canReadMovements, () => fetchAccountBalances(session.token, companyId)),
    metric(canReadMovements, () => fetchBalanceReconciliation(session.token, companyId)),
    metric(canReadReports, () => fetchCloseReadiness(session.token, companyId)),
  ]);

  const facts: AccountingFacts = {
    accounts: accountsResult.state === 'available'
      ? { state: 'available', value: accountsResult.value.filter((item) => item.status === 'active').length }
      : accountsResult,
    sources: sourcesResult.state === 'available'
      ? { state: 'available', value: sourcesResult.value.filter((item) => item.status === 'active').length }
      : sourcesResult,
    documents: documentsResult.state === 'available'
      ? { state: 'available', value: {
          total: documentsResult.value.length,
          raw: documentsResult.value.filter((item) => item.zone === 'raw').length,
          quarantine: documentsResult.value.filter((item) => item.zone === 'quarantine').length,
        } }
      : documentsResult,
    datasets: datasetsResult.state === 'available'
      ? { state: 'available', value: {
          total: datasetsResult.value.length,
          staging: datasetsResult.value.filter((item) => item.state === 'staging').length,
          validated: datasetsResult.value.filter((item) => item.state === 'validated').length,
          published: datasetsResult.value.filter((item) => item.state === 'published').length,
        } }
      : datasetsResult,
    balances: balanceResult.state !== 'available'
      ? balanceResult
      : reconciliationResult.state !== 'available'
        ? reconciliationResult
        : { state: 'available', value: {
            observations: balanceResult.value.items.length,
            statements: reconciliationResult.value.statements.length,
            balanced: reconciliationResult.value.statements.filter((item) => item.state === 'balanced').length,
          } },
    close: closeResult.state === 'available'
      ? { state: 'available', value: {
          reviewReady: closeResult.value.review_ready_period_count,
          blocked: closeResult.value.blocked_period_count,
        } }
      : closeResult,
    reports: canReadReports ? { state: 'available', value: true } : { state: 'restricted' },
  };

  const stages = deriveAccountingFlow(companyId, facts);
  const withEvidence = stages.filter((stage) => stage.status === 'done').length;
  const actionable = stages.filter((stage) => stage.status === 'ready' || stage.status === 'attention').length;

  return (
    <main className="accounting-flow-page">
      <header className="bar page-hero accounting-flow-hero">
        <div className="page-heading">
          <Link className="breadcrumb" href={`/empresas/${companyId}`}>← {company.legal_name}</Link>
          <p className="eyebrow">Recorrido de trabajo</p>
          <h1>Flujo contable</h1>
          <p className="page-heading__description">
            De la evidencia original al expediente previo al cierre, con estado,
            siguiente acción y límites visibles en cada paso.
          </p>
        </div>
        <div className="flow-hero-summary" aria-label="Resumen del recorrido">
          <strong>{withEvidence}</strong><span>etapas con evidencia</span>
          <strong>{actionable}</strong><span>acciones disponibles</span>
        </div>
      </header>

      <section className="flow-principles" aria-label="Principios del flujo">
        <span>Original inmutable</span>
        <span>Decimal exacto</span>
        <span>Linaje por campo</span>
        <span>Decisión humana</span>
        <span>Segregación de funciones</span>
      </section>

      <ol className="accounting-flow" aria-label="Etapas del flujo contable">
        {stages.map((stage) => (
          <li className={`flow-stage flow-stage--${stage.status}`} key={stage.key}>
            <div className="flow-stage__rail" aria-hidden="true">
              <span>{stage.number}</span>
            </div>
            <article className="card flow-stage__card">
              <header>
                <div>
                  <p className="eyebrow">{stage.eyebrow}</p>
                  <h2>{stage.title}</h2>
                </div>
                <span className={`flow-status flow-status--${stage.status}`}>
                  {STATUS_LABELS[stage.status]}
                </span>
              </header>
              <p>{stage.description}</p>
              <p className="flow-stage__detail">{stage.detail}</p>
              {stage.boundary ? <p className="flow-stage__boundary">{stage.boundary}</p> : null}
              <Link className="flow-stage__action" href={stage.href}>{stage.action} →</Link>
            </article>
          </li>
        ))}
      </ol>

      <section className="card accounting-flow-note" role="note">
        <div>
          <p className="eyebrow">Límite vigente</p>
          <h2>Preparación completa no significa cierre certificado</h2>
          <p>
            Las etapas conservan estados parciales, desconocidos y revisiones pendientes.
            Ningún enlace de esta vista evita permisos, RLS, linaje ni segregación.
          </p>
        </div>
        <Link href={`/auditoria?empresa=${encodeURIComponent(companyId)}`}>Consultar auditoría</Link>
      </section>
    </main>
  );
}

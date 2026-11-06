import { randomUUID } from 'node:crypto';

import Link from 'next/link';
import { notFound, redirect } from 'next/navigation';

import {
  ApiError,
  fetchAccountingPeriods,
  fetchAudit,
  fetchBalanceReconciliation,
  fetchCompany,
  fetchDatasets,
  fetchDocuments,
  fetchExpectations,
  fetchMe,
  fetchReconciliationCandidates,
  fetchReconciliationSummary,
  fetchReviewQueue,
  fetchSourcesFull,
  fetchUnmatchedMovements,
  fetchUploadSchedule,
  type AccountingPeriodClose,
  type ArtifactSummary,
  type AuditEvent,
  type BalanceReconciliationWorkspace,
  type DatasetSummary,
  type Expectation,
  type MatchReview,
  type ReconciliationSummary,
  type Source,
  type UnmatchedPage,
  type UploadSchedule,
  type CandidatePage,
} from '@/lib/api';
import { summarizeDatasets, summarizeExpectations } from '@/lib/portfolio';
import { readSession } from '@/lib/session';
import {
  buildPendingInbox,
  buildSuggestions,
  candidateExplanation,
  latestClose,
  operatingProfileOf,
  PROFILE_LABELS,
  ruleApplications,
  selectSimplePair,
  SIMPLE_CANDIDATE_TOLERANCE,
  SIMPLE_MAX_DAYS,
  unpairedMovements,
  type PendingEntry,
} from '@/lib/simple-mode';
import { SimpleHome } from './simple-home';
import type { InboxDecisionItem, SimpleInboxProps } from './simple-inbox';
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
  unsafe_or_active_pdf: 'el PDF esta danado, cifrado o contiene funciones activas',
  ocr_required: 'el PDF necesita OCR y permanece en cuarentena',
  ocr_failed: 'el OCR local no pudo terminar de forma verificable',
  ocr_invalid: 'el derivado OCR no coincide con la evidencia original',
  content_inspected_ocr: 'el PDF se inspecciono completamente mediante OCR local',
  unscannable: 'no se pudo examinar',
};

type Loaded<T> = { state: 'ok'; value: T } | { state: 'restricted' } | { state: 'unavailable' };

async function load<T>(allowed: boolean, operation: () => Promise<T>): Promise<Loaded<T>> {
  if (!allowed) return { state: 'restricted' };
  try {
    return { state: 'ok', value: await operation() };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    if (error instanceof ApiError && error.status === 403) return { state: 'restricted' };
    return { state: 'unavailable' };
  }
}

type SimpleData = {
  actorId: string;
  pending: PendingEntry[] | null;
  pendingPartial: boolean;
  close: AccountingPeriodClose | null | 'restricted' | 'unavailable';
  inbox: SimpleInboxProps | null;
  summary: ReconciliationSummary | 'restricted' | 'unavailable';
  schedule: UploadSchedule | 'restricted' | 'unavailable';
};

function commandKey(): string {
  return `smb-${randomUUID()}`;
}

function loadedOr<T>(value: Loaded<T>): T | 'restricted' | 'unavailable' {
  return value.state === 'ok' ? value.value : value.state;
}

async function loadSimpleData(
  token: string,
  companyId: string,
  permissions: readonly string[],
  datasets: DatasetSummary[] | null,
  documents: ArtifactSummary[] | null,
): Promise<SimpleData> {
  const canReadMovements = permissions.includes('movement.read');
  const pair = datasets && documents ? selectSimplePair(datasets, documents) : null;
  const [me, reviews, workspace, periods, confirmed, unmatched, candidates, summary,
    schedule] = await Promise.all([
    load(true, () => fetchMe(token)),
    load<MatchReview[]>(canReadMovements, async () =>
      (await fetchReviewQueue(token, companyId, 'open', 0, 100)).items),
    load<BalanceReconciliationWorkspace>(canReadMovements, () =>
      fetchBalanceReconciliation(token, companyId, 100)),
    load(permissions.includes('report.read'), () =>
      fetchAccountingPeriods(token, companyId, 100)),
    load<MatchReview[]>(canReadMovements, async () =>
      (await fetchReviewQueue(token, companyId, 'confirmed', 0, 100)).items),
    load<UnmatchedPage>(canReadMovements && pair !== null, () =>
      fetchUnmatchedMovements(token, companyId, pair!.leftDatasetId, pair!.rightDatasetId,
        0, 100)),
    // Tolerancia por defecto del modo simple: las retenciones y comisiones
    // aparecen como candidatos con su diferencia explicada; decide una persona.
    load<CandidatePage>(canReadMovements && pair !== null, () =>
      fetchReconciliationCandidates(token, companyId, pair!.leftDatasetId,
        pair!.rightDatasetId, SIMPLE_MAX_DAYS, 'all', 0, 50, SIMPLE_CANDIDATE_TOLERANCE)),
    load<ReconciliationSummary>(canReadMovements, () =>
      fetchReconciliationSummary(token, companyId)),
    load<UploadSchedule>(true, () => fetchUploadSchedule(token, companyId)),
  ]);
  let inbox: SimpleInboxProps | null = null;
  if (canReadMovements) {
    const openReviews = reviews.state === 'ok' ? reviews.value : [];
    const free = unmatched.state === 'ok' ? unmatched.value.items : [];
    const suggestions = candidates.state === 'ok'
      ? buildSuggestions(candidates.value.candidates, free, openReviews)
      : [];
    const decisions: InboxDecisionItem[] = [
      ...openReviews.map((review) => ({
        key: `candidate:${review.candidate_id}`,
        candidateId: review.candidate_id,
        leftMovementId: null,
        rightMovementId: null,
        title: review.confirmation_conflict
          ? 'Posible cruce en conflicto'
          : 'Posible cruce por confirmar',
        detail: `Propuesto por ${review.proposed_by_name} · ${review.date_distance_days} día(s) de diferencia`,
        explanation: candidateExplanation(review),
        conflict: review.confirmation_conflict,
        decisionKey: commandKey(),
        ruleKey: commandKey(),
      })),
      ...suggestions.map((suggestion) => ({
        key: suggestion.key,
        candidateId: null,
        leftMovementId: suggestion.leftMovementId,
        rightMovementId: suggestion.rightMovementId,
        title: suggestion.title,
        detail: suggestion.detail,
        explanation: suggestion.explanation,
        conflict: false,
        decisionKey: commandKey(),
        ruleKey: commandKey(),
      })),
    ];
    const applications = (confirmed.state === 'ok' ? ruleApplications(confirmed.value) : [])
      .map((review) => ({
        decisionId: review.decision!.decision_id,
        detail: `Regla v${review.decision!.rule_version ?? 1} · aprobada por `
          + `${review.decision!.decided_by_name} · ${review.decision!.decided_at.slice(0, 10)}`,
        revertKey: commandKey(),
      }));
    const unpaired = unpairedMovements(free, suggestions);
    inbox = {
      companyId,
      pair,
      decisions,
      applications,
      unpaired: unpaired.slice(0, 20),
      unpairedTotal: unpaired.length,
      canConfirm: permissions.includes('match.confirm'),
      canReject: permissions.includes('match.reject'),
      canPropose: permissions.includes('match.propose'),
      canCreateRule: permissions.includes('match.propose'),
      applyKey: commandKey(),
      revertKeyPrefix: commandKey(),
    };
  }
  const pending = canReadMovements
    ? buildPendingInbox(companyId, {
        reviews: reviews.state === 'ok' ? reviews.value : null,
        datasets,
        items: workspace.state === 'ok' ? workspace.value.items : null,
        statements: workspace.state === 'ok' ? workspace.value.statements : null,
      })
    : null;
  return {
    actorId: me.state === 'ok' ? me.value.subject_id : '',
    pending,
    pendingPartial: canReadMovements && (
      reviews.state !== 'ok' || workspace.state !== 'ok' || datasets === null
      || (workspace.state === 'ok' && workspace.value.truncated)),
    close: periods.state === 'ok'
      ? latestClose(periods.value.items)
      : periods.state,
    inbox,
    summary: loadedOr(summary),
    schedule: loadedOr(schedule),
  };
}

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

  const profile = operatingProfileOf(company);
  const simple = profile === 'simple'
    ? await loadSimpleData(session.token, companyId, company.permissions, datasets,
      documentsVisible ? documents : null)
    : null;

  const uploadBlock = uploadSourcesVisible ? (
    <div className="card">
      <UploadForm
        companyId={companyId}
        sources={uploadSources}
        initialSourceId={initialSourceId}
      />
      <p className="meta">
        CSV, PDF, libro de calculo, factura electronica DIAN (XML) o extracto
        MT940, hasta 25 MB. El tipo se decide por los primeros bytes, no por la
        extension.
      </p>
      <p className="meta">
        Cada archivo que se sube entra en <strong>cuarentena</strong>. Sale de ahi
        cuando su contenido se ha inspeccionado entero y no aparece nada
        sensible. Si un libro tiene varias hojas, eliges una de forma explicita
        antes de perfilar o extraer. Lo que no se puede inspeccionar se queda en
        cuarentena, y se dice por que.
      </p>
    </div>
  ) : null;

  return (
    <main className="company-home">
      <header className="bar page-hero company-hero">
        <div className="page-heading">
          <Link className="breadcrumb" href="/empresas">← Portafolio</Link>
          <h1>{company.legal_name}</h1>
          <div className="company-context">
            <span className="status-pill status-pill--ok">{company.status}</span>
            <span>{company.country_code}</span>
            <span>Autorizacion v{company.authorization_version}</span>
            <span>Perfil {PROFILE_LABELS[profile]}</span>
          </div>
        </div>
      </header>

      <nav className="workspace-nav" aria-label="Navegacion de la empresa">
          <Link href={`/empresas/${companyId}/flujo-contable`}><span aria-hidden="true">→</span> Flujo contable</Link>
          {company.permissions.includes('report.read') ? (
            <><Link href={`/informes?empresa=${companyId}`}><span aria-hidden="true">▥</span> Informes</Link>
              <Link href={`/preparacion-cierre?empresa=${companyId}`}><span aria-hidden="true">◎</span>
                Preparacion de cierre
              </Link></>
          ) : null}
          {company.permissions.includes('quality.read') ? (
            <Link href={`/calidad?empresa=${companyId}`}><span aria-hidden="true">◇</span> Calidad</Link>
          ) : null}
          {company.permissions.includes('member.manage') ? (
            <Link href={`/empresas/${companyId}/equipo`}><span aria-hidden="true">◌</span> Equipo y roles</Link>
          ) : null}
          {company.permissions.includes('movement.read') ? (
            <><Link href={`/empresas/${companyId}/saldos`}><span aria-hidden="true">≋</span> Saldos</Link>
              <Link href={`/empresas/${companyId}/conciliacion-saldos`}><span aria-hidden="true">⇄</span> Conciliar saldos</Link>
              <Link href={`/empresas/${companyId}/conciliacion`}><span aria-hidden="true">⌘</span> Cruzar movimientos</Link>
              <Link href={`/empresas/${companyId}/reglas`}><span aria-hidden="true">≡</span> Reglas</Link></>
          ) : null}
          {company.permissions.includes('document.read') ? (
            <Link href={`/empresas/${companyId}/documentos`}><span aria-hidden="true">▤</span> Documentos</Link>
          ) : null}
          <Link href={`/empresas/${companyId}/fuentes`}><span aria-hidden="true">⌁</span> Fuentes y cuentas</Link>
          <Link href={`/empresas/${companyId}/ajustes`}><span aria-hidden="true">⚙</span> Ajustes</Link>
      </nav>

      {simple ? (
        <SimpleHome
          companyId={companyId}
          actorId={simple.actorId}
          permissions={company.permissions}
          upload={uploadBlock ?? (
            <p className="meta">Tu acceso no permite subir archivos en esta empresa.</p>
          )}
          pending={simple.pending}
          pendingPartial={simple.pendingPartial}
          close={simple.close}
          inbox={simple.inbox}
          summary={simple.summary}
          schedule={simple.schedule}
        />
      ) : (
        <section className="card mode-switch" aria-labelledby="accountant-mode-heading">
          <div>
            <p className="eyebrow">Modo contador</p>
            <h2 id="accountant-mode-heading">Flujo contable en siete etapas</h2>
            <p className="meta">
              Perfil estricto: cada decision la confirma una persona distinta de
              quien la propuso.
            </p>
          </div>
          <Link href={`/empresas/${companyId}/flujo-contable`}>Abrir flujo contable →</Link>
        </section>
      )}

      <details className="card access-details">
        <summary>
          <span>
            <strong>Acceso de esta cuenta</strong>
            <small>Roles, permisos y contexto tecnico</small>
          </span>
          <span aria-hidden="true" className="details-chevron">⌄</span>
        </summary>
        <div className="access-details__content">
          <div>
            <div className="meta">Roles en esta empresa</div>
            <div className="tags">
              {company.roles.map((role) => (
                <span className="tag" key={role}>{role}</span>
              ))}
            </div>
          </div>
          <div>
            <div className="meta">Permisos que concede el servidor</div>
            <div className="tags">
              {company.permissions.map((permission) => (
                <span className="tag" key={permission}>{permission}</span>
              ))}
            </div>
          </div>
        </div>
      </details>

      {simple ? null : (<>
      <section className="workspace-section" aria-labelledby="operational-load">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Hoy</p>
            <h2 id="operational-load">Carga operativa</h2>
          </div>
          <p>Conteos de actividad y vencimiento; no son saldos ni una conciliacion.</p>
        </div>
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

      <div className="section-heading">
        <div>
          <p className="eyebrow">Entrada de datos</p>
          <h2 id="carga-documentos">Documentos</h2>
        </div>
        <Link href={`/empresas/${companyId}/documentos`}>Abrir centro de documentos →</Link>
      </div>
      {uploadBlock}

      {!documentsVisible ? (
        <p className="card">
          Este rol no puede consultar documentos. No se presenta como una lista
          vacia porque la ausencia de acceso no dice si existen o no.
        </p>
      ) : documents.length === 0 ? (
        <div className="card">
          <p>Todavia no hay documentos en esta empresa.</p>
          <Link href={`/empresas/${companyId}/documentos`}>Abrir centro de documentos</Link>
        </div>
      ) : (
        <div className="card scroll">
          <table>
            <caption className="meta">
              Ultimos 50 documentos.{' '}
              <Link href={`/empresas/${companyId}/documentos`}>
                Buscar, filtrar y recorrer todo el historico
              </Link>
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
      </>)}
    </main>
  );
}

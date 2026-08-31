import { randomUUID } from 'node:crypto';

import Link from 'next/link';
import { redirect } from 'next/navigation';

import { SignOut } from '@/app/empresas/sign-out';
import {
  ApiError,
  fetchMe,
  type AccountingPeriodClose,
  type CloseReadinessControl,
  type CloseReadinessPeriod,
} from '@/lib/api';
import {
  closeForPeriod,
  loadClosePeriodCenter,
  type ClosePeriodSnapshot,
} from '@/lib/close-period';
import {
  packetsForPeriod,
  loadCloseReviewCenter,
  type CloseReviewSnapshot,
} from '@/lib/close-review';
import {
  aggregateCloseReadinessCounts,
  availableClosePeriods,
  filterCloseReadinessPeriod,
  formatClosePeriod,
  loadCloseReadinessCenter,
  selectCloseReadinessCompanies,
  selectClosePeriod,
  type CloseReadinessSnapshot,
  type StatementLineageSnapshot,
} from '@/lib/close-readiness';
import { readSession } from '@/lib/session';

import {
  CloseAccountingPeriodControl,
  CloseReviewDecisionControls,
  PrepareCloseReviewForm,
  ReopenDecisionControls,
  RequestPeriodReopenForm,
} from './review-controls';

export const dynamic = 'force-dynamic';

type QueryValue = string | string[] | undefined;

const CONTROL_LABELS: Record<string, string> = {
  expected_sources: 'Fuentes esperadas',
  expectations_satisfied: 'Ciclos recibidos',
  dataset_evidence: 'Evidencia procesada',
  published_datasets: 'Datasets publicados',
  verified_completeness: 'Completitud verificada',
  complete_lineage: 'Linaje completo',
  rejected_rows: 'Filas rechazadas',
  accounting_dates: 'Fechas contables',
  reconciliation_reviews: 'Revisiones de conciliacion',
  quality_alerts: 'Alertas altas',
  pending_corrections: 'Correcciones pendientes',
  account_balances: 'Saldos por cuenta',
  completeness_assessments: 'Evaluaciones de completitud',
  reconciliation_statements: 'Estado de conciliacion',
  reconciliation_statement_lineage: 'Linaje del estado',
  product_close: 'Cierre productivo',
};

const STATE_LABELS: Record<CloseReadinessControl['state'], string> = {
  pass: 'Cumple',
  blocked: 'Bloquea',
  unavailable: 'Aun no disponible',
};

const COVERAGE_LABELS: Record<string, string> = {
  covered: 'Estado vigente y balanceado',
  missing_assessment: 'Falta evaluacion elegible',
  missing_statement: 'Falta estado de conciliacion',
  stale_inputs: 'El estado usa evidencia anterior',
  review_required: 'La conciliacion requiere revision',
};

const LINEAGE_NODE_LABELS: Record<string, string> = {
  financial_fact_field: 'Hecho financiero',
  decision: 'Decision versionada',
};

function StatementLineageDrilldown({ lineage }: {
  lineage: StatementLineageSnapshot | undefined;
}) {
  if (!lineage || lineage.access === 'unavailable') {
    return <p className="meta" role="status">Trazabilidad no disponible; no se presume completa.</p>;
  }
  if (lineage.access === 'restricted') {
    return <p className="meta">Sin permiso para inspeccionar la trazabilidad.</p>;
  }
  if (!lineage.result) {
    return <p className="meta" role="status">Trazabilidad sin respuesta verificable.</p>;
  }
  return (
    <details className="statement-lineage">
      <summary>Ver trazabilidad ({lineage.result.inputs.length} insumo(s))</summary>
      <p className="meta">
        Vista solo de identidades, versiones y huellas SHA-256. No contiene importes,
        valores fuente ni autoridad para cerrar.
      </p>
      {lineage.result.inputs.length ? (
        <ol className="statement-lineage__list">
          {lineage.result.inputs.map((input) => (
            <li key={`${input.node_type}:${input.entity_ref}:${input.field_name}`}>
              <strong>{LINEAGE_NODE_LABELS[input.node_type] ?? input.node_type}</strong>
              <span>{input.field_name} · {input.operation}</span>
              <dl>
                <div><dt>Entidad</dt><dd><code>{input.entity_ref}</code></dd></div>
                <div><dt>Huella</dt><dd><code className="digest">{input.value_digest}</code></dd></div>
                <div><dt>Ejecucion</dt><dd><code>{input.processing_run_id}</code></dd></div>
                <div><dt>Motor</dt><dd><code>{input.engine_release_id}</code></dd></div>
                <div><dt>Esquema</dt><dd>{input.canonical_schema_version}</dd></div>
              </dl>
            </li>
          ))}
        </ol>
      ) : (
        <p role="status">El statement no expone insumos materializados.</p>
      )}
    </details>
  );
}

const REVIEW_STATUS_LABELS: Record<string, string> = {
  pending_review: 'Pendiente de revision',
  evidence_reviewed: 'Evidencia revisada',
  changes_requested: 'Cambios solicitados',
};

const REVIEW_REASON_LABELS: Record<string, string> = {
  controls_reviewed: 'Controles revisados',
  missing_evidence: 'Falta evidencia',
  inconsistent_scope: 'Alcance inconsistente',
  quality_blocker: 'Bloqueo de calidad',
  lineage_gap: 'Falta trazabilidad',
  reconciliation_gap: 'Falta completar conciliacion',
};

function formatReviewTimestamp(value: string): string {
  return `${new Date(value).toISOString().slice(0, 16).replace('T', ' ')} UTC`;
}

function CloseReviewPanel({
  companyId,
  period,
  actorId,
  snapshot,
  periodClose,
  periodPermissions,
}: {
  companyId: string;
  period: CloseReadinessPeriod;
  actorId: string;
  snapshot: CloseReviewSnapshot | undefined;
  periodClose: AccountingPeriodClose | undefined;
  periodPermissions: string[];
}) {
  const accessibleLabel = `Expediente de revision ${formatClosePeriod(
    period.period_start, period.period_end)}`;
  if (!snapshot || snapshot.access !== 'available') {
    return (
      <section className="close-review-panel" aria-label={accessibleLabel}>
        <h4>Expediente de revision de evidencia</h4>
        <p className="meta" role="status">
          Los expedientes no estan disponibles. No se presume que el periodo fue revisado.
        </p>
      </section>
    );
  }
  const packets = packetsForPeriod(snapshot, period.period_start, period.period_end);
  const reviewers = snapshot.reviewers.filter((reviewer) => reviewer.subject_id !== actorId);
  const canPrepare = snapshot.permissions.includes('close.prepare');
  const canApprove = snapshot.permissions.includes('close.approve');
  const activeClose = periodClose?.status === 'reopened' ? undefined : periodClose;
  const latestPacketId = packets[0]?.packet_id;
  return (
    <section className="close-review-panel" aria-label={accessibleLabel}>
      <header>
        <div>
          <p className="eyebrow">Control previo sin efecto financiero</p>
          <h4>Expediente de revision de evidencia</h4>
        </div>
        <span className="tag">{packets.length} version(es)</span>
      </header>
      <p className="meta">
        Fija estados, conteos, identificadores y huellas SHA-256. No contiene
        importes ni habilita, ejecuta o certifica un cierre.
      </p>
      {canPrepare ? (
        <PrepareCloseReviewForm companyId={companyId}
          periodStart={period.period_start} periodEnd={period.period_end}
          reviewers={reviewers} commandKey={`cls005-prepare-${randomUUID()}`} />
      ) : null}

      {packets.length ? (
        <ol className="close-review-list">
          {packets.map((packet) => {
            const assignedHere = packet.assigned_reviewer_id === actorId;
            const canDecide = canApprove && assignedHere && packet.reviewer_eligible
              && packet.status === 'pending_review';
            return (
              <li key={packet.packet_id} id={`expediente-${packet.packet_id}`}>
                <header>
                  <div>
                    <strong>Version {packet.version}</strong>
                    <span className={`tag close-review-state--${packet.status}`}>
                      {REVIEW_STATUS_LABELS[packet.status] ?? packet.status}
                    </span>
                  </div>
                  <span className="meta">{formatReviewTimestamp(packet.prepared_at)}</span>
                </header>
                <dl className="close-review-details">
                  <div><dt>Preparador</dt><dd>{packet.preparer_name}</dd></div>
                  <div><dt>Revisor asignado</dt><dd>{packet.reviewer_name}</dd></div>
                  <div><dt>Diagnostico fijado</dt><dd>
                    {packet.diagnostic_status === 'ready_for_review'
                      ? 'Listo para revision' : 'Bloqueado'}
                  </dd></div>
                  <div><dt>Contenido</dt><dd>
                    {packet.manifest.sources.length} fuente(s),{' '}
                    {packet.manifest.accounts.length} cuenta(s),{' '}
                    {packet.manifest.controls.length} control(es)
                  </dd></div>
                  <div className="close-review-details__digest"><dt>Huella</dt>
                    <dd><code className="digest">{packet.manifest_digest}</code></dd></div>
                </dl>
                {packet.decision ? (
                  <>
                    <p className="notice ok" role="status">
                      <strong>{REVIEW_STATUS_LABELS[packet.decision]}</strong>{' '}
                      por {packet.decider_name}.{' '}
                      {packet.reason_code
                        ? REVIEW_REASON_LABELS[packet.reason_code] ?? packet.reason_code
                        : null}.
                    </p>
                    {packet.decision === 'evidence_reviewed' && !activeClose
                        && canApprove && packet.decided_by === actorId
                        && packet.packet_id === latestPacketId ? (
                      <CloseAccountingPeriodControl companyId={companyId} packet={packet}
                        commandKey={`cls006-close-${randomUUID()}`} />
                    ) : null}
                  </>
                ) : canDecide ? (
                  <CloseReviewDecisionControls companyId={companyId} packet={packet}
                    reviewCommandKey={`cls005-reviewed-${randomUUID()}`}
                    changesCommandKey={`cls005-changes-${randomUUID()}`} />
                ) : (
                  <p className="meta">
                    {assignedHere && !packet.reviewer_eligible
                      ? 'La asignacion ya no es elegible; se requiere una version nueva.'
                      : 'Solo el revisor asignado y vigente puede decidir este expediente.'}
                  </p>
                )}
              </li>
            );
          })}
        </ol>
      ) : (
        <p className="meta" role="status">Aun no hay un expediente fijado para este periodo.</p>
      )}

      {periodClose ? (
        <section className={`notice ${periodClose.status === 'reopened' ? '' : 'ok'}`}
          aria-label="Estado del periodo contable">
          <p className="eyebrow">Estado contable versionado</p>
          <h5>
            {periodClose.status === 'closed' ? 'Periodo cerrado'
              : periodClose.status === 'reopen_requested' ? 'Reapertura solicitada'
                : 'Periodo reabierto'} · version {periodClose.version}
          </h5>
          <p className="meta">
            Cerrado por {periodClose.closer_name} el{' '}
            {formatReviewTimestamp(periodClose.closed_at)}. Snapshot{' '}
            <code className="digest">{periodClose.snapshot_digest}</code>
          </p>
          {periodClose.reopen_request ? (
            <p>
              <strong>Solicitud:</strong> {periodClose.reopen_request.reason_code} por{' '}
              {periodClose.reopen_request.requester_name}.{' '}
              {periodClose.reopen_request.decision
                ? `Decision: ${periodClose.reopen_request.decision}.`
                : 'Pendiente de una segunda persona.'}
            </p>
          ) : null}
          {periodClose.status === 'closed'
              && periodPermissions.includes('close.reopen.request') ? (
            <RequestPeriodReopenForm companyId={companyId} close={periodClose}
              commandKey={`cls006-reopen-request-${randomUUID()}`} />
          ) : null}
          {periodClose.status === 'reopen_requested'
              && periodPermissions.includes('close.reopen.approve')
              && periodClose.reopen_request?.requested_by !== actorId ? (
            <ReopenDecisionControls companyId={companyId} close={periodClose}
              approveCommandKey={`cls006-reopen-approve-${randomUUID()}`}
              rejectCommandKey={`cls006-reopen-reject-${randomUUID()}`} />
          ) : null}
        </section>
      ) : null}
    </section>
  );
}

function PeriodCard({ period, companyId, actorId, statementLineages, review,
  periodSnapshot }: {
  period: CloseReadinessPeriod;
  companyId: string;
  actorId: string;
  statementLineages: Record<string, StatementLineageSnapshot>;
  review: CloseReviewSnapshot | undefined;
  periodSnapshot: ClosePeriodSnapshot | undefined;
}) {
  return (
    <article className="card close-period">
      <header className="close-period__header">
        <div>
          <p className="eyebrow">Periodo contable</p>
          <h3>{formatClosePeriod(period.period_start, period.period_end)}</h3>
        </div>
        <span className={`tag close-state close-state--${period.status}`}>
          {period.status === 'ready_for_review'
            ? 'Evidencia lista para revision'
            : 'Evidencia bloqueada'}
        </span>
      </header>

      <dl className="close-control-grid">
        {period.controls.map((control) => (
          <div className={`close-control close-control--${control.state}`} key={control.code}>
            <dt>{CONTROL_LABELS[control.code] ?? control.code}</dt>
            <dd>{STATE_LABELS[control.state]}</dd>
            <dd className="close-control__count">
              {control.count} {control.count === 1 ? 'observacion' : 'observaciones'}
            </dd>
            <dd className="meta">{control.detail}</dd>
          </div>
        ))}
      </dl>

      <details className="close-evidence">
        <summary>
          Ver evidencia por fuente ({period.source_count} esperada(s),{' '}
          {period.selected_dataset_count} con dataset seleccionado)
        </summary>
        {period.sources.length ? (
          <div className="scroll">
            <table>
              <thead><tr><th scope="col">Fuente</th><th scope="col">Recepcion</th>
                <th scope="col">Dataset elegido</th><th scope="col">Completitud</th>
                <th scope="col">Linaje</th><th scope="col">Filas</th></tr></thead>
              <tbody>{period.sources.map((source) => (
                <tr key={source.expectation_id}>
                  <th scope="row">{source.source_name}</th>
                  <td>{source.expectation_state}</td>
                  <td>{source.dataset_state ?? 'Sin dataset'}</td>
                  <td>{source.completeness_state ?? 'Sin evaluar'}</td>
                  <td>{source.lineage_state ?? 'Sin evaluar'}</td>
                  <td>{source.movement_count} movimientos · {source.rejected_count} rechazadas</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : (
          <p role="status">No hay fuentes configuradas en esta ventana.</p>
        )}
      </details>

      <details className="close-evidence">
        <summary>
          Ver cobertura por cuenta ({period.account_reconciliations.length} cuenta(s))
        </summary>
        {period.account_reconciliations.length ? (
          <div className="scroll">
            <table>
              <thead><tr><th scope="col">Cuenta</th><th scope="col">Fuentes</th>
                <th scope="col">Evaluaciones</th><th scope="col">Statement</th>
                <th scope="col">Cobertura</th><th scope="col">Linaje</th></tr></thead>
              <tbody>{period.account_reconciliations.map((account) => (
                <tr key={account.financial_account_id}>
                  <th scope="row">
                    {account.account_name ?? `Cuenta ${account.financial_account_id.slice(0, 8)}`}
                  </th>
                  <td>{account.source_count}</td>
                  <td>{account.assessment_count}</td>
                  <td>{account.statement_version
                    ? `v${account.statement_version} · ${account.statement_state}`
                    : 'Sin statement'}</td>
                  <td>{COVERAGE_LABELS[account.coverage_state] ?? account.coverage_state}</td>
                  <td>
                    <span>{account.statement_lineage_state ?? 'Sin statement'}</span>
                    {account.statement_id ? (
                      <StatementLineageDrilldown
                        lineage={statementLineages[account.statement_id]} />
                    ) : null}
                  </td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : (
          <p role="status">No hay cuentas asignadas a las fuentes de este periodo.</p>
        )}
      </details>

      <CloseReviewPanel companyId={companyId} period={period}
        actorId={actorId} snapshot={review}
        periodClose={closeForPeriod(periodSnapshot, period.period_start, period.period_end)}
        periodPermissions={periodSnapshot?.permissions ?? []} />

      <footer className="close-period__actions">
        <Link href={`/recordatorios?empresa=${companyId}`}>Revisar ciclos</Link>
        <Link href={`/calidad?empresa=${companyId}`}>Revisar calidad</Link>
        <Link href="/revisiones">Revisar conciliaciones</Link>
      </footer>
    </article>
  );
}

function CompanyReadiness({ snapshot, actorId, review, periodSnapshot }: {
  snapshot: CloseReadinessSnapshot;
  actorId: string;
  review: CloseReviewSnapshot | undefined;
  periodSnapshot: ClosePeriodSnapshot | undefined;
}) {
  const { company, result, statementLineages } = snapshot;
  if (!result) {
    return (
      <article className="card close-company close-company--unavailable">
        <h2>{company.legal_name}</h2>
        <p role="status">
          {snapshot.access === 'restricted' || snapshot.access === 'revoked'
            ? 'Sin acceso vigente al diagnostico. No se interpreta como cero bloqueos.'
            : 'No se pudo actualizar esta empresa. No se interpreta como lista para cierre.'}
        </p>
      </article>
    );
  }
  return (
    <section className="close-company" aria-labelledby={`close-${company.company_id}`}>
      <header className="close-company__header">
        <div>
          <p className="eyebrow">{result.source_count} fuente(s) en la ventana</p>
          <h2 id={`close-${company.company_id}`}>{company.legal_name}</h2>
        </div>
        <Link href={`/empresas/${company.company_id}`}>Abrir empresa</Link>
      </header>
      {result.items.length ? (
        <div className="close-period-list">
          {result.items.map((period) => (
            <PeriodCard key={`${period.period_start}:${period.period_end}`}
              period={period} companyId={company.company_id}
              actorId={actorId} review={review}
              statementLineages={statementLineages}
              periodSnapshot={periodSnapshot} />
          ))}
        </div>
      ) : (
        <p className="card" role="status">
          No hay periodos configurados en esta ventana. Esto no significa que la
          empresa este lista ni que exista un cierre certificado.
        </p>
      )}
    </section>
  );
}

export default async function CloseReadinessPage({ searchParams }: {
  searchParams: Promise<Record<string, QueryValue>>;
}) {
  const session = await readSession();
  if (!session) redirect('/entrar');
  const query = await searchParams;

  let me;
  try {
    me = await fetchMe(session.token);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    throw error;
  }
  const companies = selectCloseReadinessCompanies(me.companies, query.empresa);
  const selected = companies.length === 1 ? companies[0]?.company_id : 'todas';
  let snapshots;
  let reviewSnapshots;
  let periodSnapshots;
  try {
    [snapshots, reviewSnapshots, periodSnapshots] = await Promise.all([
      loadCloseReadinessCenter(session.token, companies),
      loadCloseReviewCenter(session.token, companies),
      loadClosePeriodCenter(session.token, companies),
    ]);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    throw error;
  }
  const availablePeriods = availableClosePeriods(snapshots);
  const selectedPeriod = selectClosePeriod(availablePeriods, query.periodo);
  const displayedSnapshots = filterCloseReadinessPeriod(snapshots, selectedPeriod);
  const reviewsByCompany = new Map(
    reviewSnapshots.map((snapshot) => [snapshot.company.company_id, snapshot]),
  );
  const periodsByCompany = new Map(
    periodSnapshots.map((snapshot) => [snapshot.company.company_id, snapshot]),
  );
  const totals = aggregateCloseReadinessCounts(displayedSnapshots);
  const partial = snapshots.filter((snapshot) => snapshot.access !== 'available');

  return (
    <main>
      <header className="bar">
        <div><Link href="/empresas">← Portafolio</Link>
          <h1>Preparacion de cierre</h1><span className="who">{me.display_name}</span>
        </div>
        <SignOut />
      </header>

      <p className="lede">
        Centro de evidencia y bloqueos por empresa y periodo. Es un diagnostico
        explicable que permite cerrar solo tras revision independiente. El cierre
        bloquea nuevas escrituras del periodo, pero no certifica estados financieros.
      </p>
      <p className="notice close-readiness-warning" role="status">
        <strong>El cierre exige expediente revisado y segregacion de funciones.</strong>{' '}
        {totals.reviewReadyPeriods
          ? `${totals.reviewReadyPeriods} periodo(s) tienen evidencia lista para revision y cierre controlado.`
          : 'Los periodos visibles conservan bloqueos de evidencia o conciliacion.'}
      </p>

      <form method="get" className="close-toolbar" aria-label="Filtrar preparacion de cierre">
        <label>Empresa<select name="empresa" defaultValue={selected}>
          <option value="todas">Todas las empresas autorizadas</option>
          {me.companies.map((company) => (
            <option key={company.company_id} value={company.company_id}>
              {company.legal_name}
            </option>
          ))}
        </select></label>
        <label>Periodo<select name="periodo" defaultValue={selectedPeriod}>
          <option value="todos">Ultimos periodos visibles</option>
          {availablePeriods.map((period) => (
            <option key={period.key} value={period.key}>
              {formatClosePeriod(period.start, period.end)}
            </option>
          ))}
        </select></label>
        <button type="submit">Actualizar diagnostico</button>
      </form>

      {partial.length ? (
        <p className="notice" role="status">
          Vista parcial: {partial.length} empresa(s) no pudieron consultarse o ya no
          estan autorizadas. No se presentan como cero bloqueos.
        </p>
      ) : null}

      <dl className="close-summary" aria-label="Resumen diagnostico multiempresa">
        <div><dt>Periodos visibles</dt><dd>{totals.periods}</dd></div>
        <div><dt>Periodos bloqueados</dt><dd>{totals.blockedPeriods}</dd></div>
        <div><dt>Listos para revision</dt><dd>{totals.reviewReadyPeriods}</dd></div>
        <div><dt>Fuentes esperadas</dt><dd>{totals.sources}</dd></div>
        <div><dt>Revisiones abiertas</dt><dd>{totals.openReviews}</dd></div>
        <div><dt>Alertas altas</dt><dd>{totals.highAlerts}</dd></div>
        <div><dt>Correcciones pendientes</dt><dd>{totals.pendingCorrections}</dd></div>
      </dl>
      <p className="meta close-aggregation-note">
        El resumen suma solo conteos de trabajo. No combina importes, monedas ni saldos.
      </p>

      <div className="close-company-list">
        {displayedSnapshots.map((snapshot) => (
          <CompanyReadiness key={snapshot.company.company_id} snapshot={snapshot}
            actorId={me.subject_id}
            review={reviewsByCompany.get(snapshot.company.company_id)}
            periodSnapshot={periodsByCompany.get(snapshot.company.company_id)} />
        ))}
      </div>
    </main>
  );
}

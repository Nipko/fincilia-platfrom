import Link from 'next/link';
import { notFound, redirect } from 'next/navigation';

import {
  ApiError,
  fetchAccountBalances,
  fetchBalanceEvidence,
  fetchBalanceReconciliation,
  fetchCompany,
  type BalanceReconciliationStatement,
  type CompletenessControlResult,
} from '@/lib/api';
import { readSession } from '@/lib/session';

import {
  AssessmentControl,
  ItemControl,
  ItemDecisionControl,
  StatementControl,
} from './reconciliation-controls';

export const dynamic = 'force-dynamic';

const STATE_LABELS: Record<string, string> = {
  verified: 'Verificado', mismatch: 'No coincide', unknown: 'Desconocido',
  accepted_exception: 'Excepcion aceptada', review_required: 'Requiere revision',
  balanced: 'Diferencia explicada', proposed: 'Propuesta', confirmed: 'Confirmada',
  rejected: 'Rechazada', reversed: 'Revertida', match: 'Coincide',
  not_applicable: 'No aplica',
};

const CONTROL_LABELS: Record<string, string> = {
  provenance_integrity: 'Integridad de evidencia', record_count: 'Cantidad de filas',
  account_identity: 'Identidad de cuenta', currency_consistency: 'Moneda consistente',
  period_coverage: 'Cobertura del periodo',
};

const REASON_LABELS: Record<string, string> = {
  bank_fee_pending: 'Comision bancaria pendiente',
  deposit_in_transit: 'Deposito en transito',
  documented_timing: 'Diferencia temporal documentada',
  outstanding_payment: 'Pago pendiente',
  other_documented: 'Otro motivo documentado',
};

function exactMoney(value: string): string {
  return value.replace(/(\.\d*?[1-9])0+$|\.0+$/, '$1');
}

function stateClass(state: string): string {
  return ['verified', 'balanced', 'confirmed', 'match'].includes(state) ? '' : 'denied';
}

function ControlBadge({ control }: { control: CompletenessControlResult }) {
  return (
    <li className={`reconciliation-control reconciliation-control--${control.outcome}`}>
      <strong>{CONTROL_LABELS[control.control_type] ?? control.control_type}</strong>
      <span className={`outcome ${stateClass(control.outcome)}`}>
        {STATE_LABELS[control.outcome] ?? control.outcome}
      </span>
      {control.reason ? <small>{control.reason}</small> : null}
    </li>
  );
}

function Equation({ statement }: { statement: BalanceReconciliationStatement }) {
  return (
    <dl className="reconciliation-equation" aria-label={`Ecuacion version ${statement.version}`}>
      <div><dt>Saldo banco</dt><dd>{exactMoney(statement.bank_closing_balance)}</dd></div>
      <span aria-hidden="true">+</span>
      <div><dt>Adiciones</dt><dd>{exactMoney(statement.confirmed_additions_to_bank)}</dd></div>
      <span aria-hidden="true">−</span>
      <div><dt>Deducciones</dt><dd>{exactMoney(statement.confirmed_deductions_from_bank)}</dd></div>
      <span aria-hidden="true">=</span>
      <div><dt>Banco ajustado</dt><dd>{exactMoney(statement.adjusted_bank_balance)}</dd></div>
      <span aria-hidden="true">−</span>
      <div><dt>Libros</dt><dd>{exactMoney(statement.books_closing_balance)}</dd></div>
      <span aria-hidden="true">=</span>
      <div className="reconciliation-equation__difference">
        <dt>Diferencia</dt><dd>{exactMoney(statement.unexplained_difference)} {statement.currency_code}</dd>
      </div>
    </dl>
  );
}

export default async function BalanceReconciliationPage({ params }: {
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
    if (error instanceof ApiError && [403, 404].includes(error.status)) notFound();
    throw error;
  }
  if (!company.permissions.includes('movement.read')) notFound();
  const canPrepare = company.permissions.includes('close.prepare');
  const canApprove = company.permissions.includes('close.approve');

  let workspace;
  let balances;
  let evidence;
  try {
    [workspace, balances, evidence] = await Promise.all([
      fetchBalanceReconciliation(session.token, companyId),
      fetchAccountBalances(session.token, companyId, 100),
      canPrepare
        ? fetchBalanceEvidence(session.token, companyId, 50)
        : Promise.resolve({ limit: 50, truncated: false, items: [] }),
    ]);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    if (error instanceof ApiError && [403, 404].includes(error.status)) notFound();
    throw error;
  }
  const latestStatements = [...new Map(
    workspace.statements.map((item) => [item.statement_root_id, item]),
  ).values()];
  const balanced = latestStatements.filter((item) => item.state === 'balanced').length;
  const unknown = workspace.assessments.filter((item) => item.state !== 'verified').length;
  const pendingItems = workspace.items.filter((item) => item.state === 'proposed').length;

  return (
    <main>
      <header className="bar">
        <div>
          <p className="eyebrow">FNC-CLS-003 · diagnostico reproducible</p>
          <h1>Conciliacion de saldos</h1>
          <span className="who">{company.legal_name}</span>
        </div>
        <nav aria-label="Navegacion de conciliacion de saldos">
          <Link href={`/empresas/${companyId}/saldos`}>Saldos</Link>{' '}
          <Link href={`/empresas/${companyId}/conciliacion`}>Cruce de movimientos</Link>{' '}
          <Link href={`/preparacion-cierre?empresa=${companyId}`}>Preparacion de cierre</Link>{' '}
          <Link href={`/empresas/${companyId}`}>Empresa</Link>
        </nav>
      </header>

      <p className="lede">
        Une saldos observados, controles de completitud y partidas documentadas en
        versiones que nunca reescriben el pasado.
      </p>
      <p className="notice close-readiness-warning" role="status">
        <strong>Una diferencia explicada no es un cierre certificado.</strong>{' '}
        Esta estacion no publica asientos, no acepta excepciones contables y no
        ejecuta cierre ni reapertura.
      </p>

      <dl className="reconciliation-summary" aria-label="Resumen de conciliacion">
        <div><dt>Fuentes esperadas</dt><dd>{workspace.totals.expectations}</dd></div>
        <div><dt>Evaluaciones con alerta</dt><dd>{unknown}</dd></div>
        <div><dt>Estados vigentes</dt><dd>{latestStatements.length}</dd></div>
        <div><dt>Diferencia explicada</dt><dd>{balanced}</dd></div>
        <div><dt>Partidas / por revisar</dt><dd>{workspace.totals.items} / {pendingItems}</dd></div>
      </dl>

      <section aria-labelledby="completitud-title">
        <div className="section-heading">
          <div><p className="eyebrow">1 · evidencia antes que ecuacion</p>
            <h2 id="completitud-title">Completitud por fuente y periodo</h2></div>
          <p>Ausente o desconocido bloquea; nunca se interpreta como cero.</p>
        </div>
        {workspace.expectations.length ? (
          <div className="card scroll">
            <table>
              <thead><tr><th scope="col">Fuente</th><th scope="col">Periodo</th>
                <th scope="col">Evidencia</th><th scope="col">Evaluacion</th></tr></thead>
              <tbody>{workspace.expectations.map((item) => (
                <tr key={item.expectation_id}>
                  <th scope="row">{item.source_name}<br /><small>{item.account_name ?? 'Sin cuenta'}</small></th>
                  <td>{item.period_start}–{item.period_end}</td>
                  <td><span className={`outcome ${item.has_artifact ? '' : 'denied'}`}>
                    {item.has_artifact ? 'Documento asociado' : 'Pendiente'}
                  </span></td>
                  <td>{canPrepare
                    ? <AssessmentControl companyId={companyId} expectation={item} />
                    : <span className="meta">Solo lectura</span>}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : <p className="card" role="status">No hay ciclos esperados. Configura primero la fuente y su periodo.</p>}

        {workspace.assessments.length ? (
          <div className="reconciliation-assessments">
            {workspace.assessments.map((item) => (
              <article className="card" key={item.assessment_id}>
                <header className="reconciliation-card-header">
                  <div><h3>{item.source_name}</h3>
                    <p className="meta">{item.period_start}–{item.period_end} · {item.account_name}</p></div>
                  <span className={`outcome ${stateClass(item.state)}`}>
                    {STATE_LABELS[item.state] ?? item.state}
                  </span>
                </header>
                <ul className="reconciliation-controls">
                  {item.controls.map((control) => <ControlBadge key={control.control_result_id} control={control} />)}
                </ul>
                <p className="meta">Linaje: {item.lineage_state}</p>
              </article>
            ))}
          </div>
        ) : null}
      </section>

      <section className="card reconciliation-workbench" aria-labelledby="calcular-title">
        <div><p className="eyebrow">2 · entradas fijadas</p><h2 id="calcular-title">Calcular estado</h2></div>
        {canPrepare ? (
          <StatementControl companyId={companyId} balances={balances.items}
            assessments={workspace.assessments} />
        ) : <p role="status">Necesitas <code>close.prepare</code> para crear una version.</p>}
      </section>

      <section aria-labelledby="estados-title">
        <div className="section-heading"><div><p className="eyebrow">3 · historico append-only</p>
          <h2 id="estados-title">Estados calculados</h2></div>
          <p>{workspace.statements.length} version(es), {latestStatements.length} estado(s) logico(s).</p>
        </div>
        {workspace.statements.length ? (
          <div className="reconciliation-statements">
            {workspace.statements.map((item) => (
              <article className={`card reconciliation-statement reconciliation-statement--${item.state}`}
                key={item.statement_id}>
                <header className="reconciliation-card-header">
                  <div><p className="eyebrow">Version {item.version}</p><h3>{item.account_name}</h3>
                    <p className="meta">{item.period_start}–{item.period_end} · {item.currency_code}</p></div>
                  <span className={`outcome ${stateClass(item.state)}`}>
                    {STATE_LABELS[item.state] ?? item.state}
                  </span>
                </header>
                <Equation statement={item} />
                <footer className="meta">
                  {item.completeness_assessment_ids.length} evaluacion(es) ·{' '}
                  {item.confirmed_reconciling_item_ids.length} partida(s) contada(s) ·{' '}
                  linaje del estado {item.lineage_state}
                </footer>
              </article>
            ))}
          </div>
        ) : <p className="card" role="status">No hay estados. Una ausencia no significa que los saldos cuadren.</p>}
      </section>

      <section className="reconciliation-two-column" aria-label="Partidas conciliatorias">
        <div className="card"><p className="eyebrow">4 · explicar sin editar</p><h2>Proponer partida</h2>
          {canPrepare ? <ItemControl companyId={companyId} statements={workspace.statements}
            evidence={evidence.items} /> : <p>Necesitas <code>close.prepare</code>.</p>}
        </div>
        <div><h2>Revision independiente</h2>
          {workspace.items.length ? <div className="reconciliation-item-list">
            {workspace.items.map((item) => <article className="card" key={item.item_decision_id}>
              <header className="reconciliation-card-header"><strong>
                {item.adjustment_side === 'add_to_bank' ? 'Suma a banco' : 'Resta de banco'}
              </strong><span className={`outcome ${stateClass(item.state)}`}>
                {STATE_LABELS[item.state] ?? item.state}</span></header>
              <p className="reconciliation-item-amount">{exactMoney(item.amount)} {item.currency_code}</p>
              <p className="meta">{REASON_LABELS[item.reason_code] ?? item.reason_code} ·{' '}
                decision v{item.decision_version} · {item.lineage_state}</p>
              <ItemDecisionControl companyId={companyId} item={item} canApprove={canApprove} />
            </article>)}
          </div> : <p className="card" role="status">No hay partidas propuestas.</p>}
        </div>
      </section>

      {(workspace.truncated || balances.truncated || evidence.truncated) ? <p className="notice" role="status">
        Vista acotada a evidencia reciente; no se afirma cobertura total.
      </p> : null}
    </main>
  );
}

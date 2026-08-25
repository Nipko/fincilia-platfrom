'use client';

import { useActionState } from 'react';

import {
  assessCompletenessAction,
  decideReconcilingItemAction,
  evaluateBalanceReconciliationAction,
  proposeReconcilingItemAction,
  type BalanceReconciliationActionState,
} from '@/app/actions';
import type {
  AccountBalance,
  BalanceEvidence,
  BalanceReconciliationStatement,
  CompletenessAssessment,
  ReconciliationExpectation,
  ReconcilingItem,
} from '@/lib/api';

const INITIAL: BalanceReconciliationActionState = { error: null, done: null };
const STATE_LABELS: Record<string, string> = {
  verified: 'Verificada', mismatch: 'No coincide', unknown: 'Desconocida',
  accepted_exception: 'Excepcion aceptada',
};

function Feedback({ state }: { state: BalanceReconciliationActionState }) {
  return <>
    {state.error ? <p className="error" role="alert">{state.error}</p> : null}
    {state.done ? <p className="notice success" role="status">{state.done}</p> : null}
  </>;
}

export function AssessmentControl({ companyId, expectation }: {
  companyId: string;
  expectation: ReconciliationExpectation;
}) {
  const [state, action, pending] = useActionState(assessCompletenessAction, INITIAL);
  const eligible = expectation.state === 'satisfied' && expectation.has_artifact;
  return (
    <form action={action} className="reconciliation-inline-action">
      <input type="hidden" name="companyId" value={companyId} />
      <input type="hidden" name="expectationId" value={expectation.expectation_id} />
      <button type="submit" disabled={pending || !eligible}>
        {pending ? 'Evaluando…' : expectation.assessed ? 'Reevaluar evidencia' : 'Evaluar completitud'}
      </button>
      {!eligible ? <span className="meta">Requiere un documento publicado.</span> : null}
      <Feedback state={state} />
    </form>
  );
}

function balanceLabel(balance: AccountBalance): string {
  const exact = balance.amount.replace(/(\.\d*?[1-9])0+$|\.0+$/, '$1');
  return `${balance.account_name} · ${exact} ${balance.currency_code} · ${balanceLocalDate(balance)}`;
}

function balanceLocalDate(balance: AccountBalance): string {
  if (!balance.source_timezone) return balance.as_of.slice(0, 10);
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: balance.source_timezone, year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(new Date(balance.as_of));
  const value = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${value.year}-${value.month}-${value.day}`;
}

export function StatementControl({ companyId, balances, assessments }: {
  companyId: string;
  balances: AccountBalance[];
  assessments: CompletenessAssessment[];
}) {
  const [state, action, pending] = useActionState(
    evaluateBalanceReconciliationAction, INITIAL);
  const bank = balances.filter((item) => item.balance_type === 'closing');
  const books = balances.filter((item) => item.balance_type === 'ledger');
  const initialBank = bank[0];
  const initialBooks = books[0];
  const scopedCandidates = initialBank && initialBooks
    ? assessments.filter((item) => {
      const bankDate = balanceLocalDate(initialBank);
      const booksDate = balanceLocalDate(initialBooks);
      return item.financial_account_id === initialBank.financial_account_id &&
        initialBooks.financial_account_id === initialBank.financial_account_id &&
        initialBooks.currency_code === initialBank.currency_code &&
        item.period_start <= bankDate && bankDate <= item.period_end &&
        item.period_start <= booksDate && booksDate <= item.period_end;
    })
    : [];
  // Un estado admite una sola evaluacion por fuente. Si hay periodos
  // historicos superpuestos, la API ordena lo reciente primero y la UI toma
  // solo esa version, en vez de enviar una cobertura doble ambigua.
  const scopedAssessments = [...new Map(
    scopedCandidates.map((item) => [item.data_source_id, item]),
  ).values()];
  const ready = bank.length > 0 && books.length > 0 && scopedAssessments.length > 0;
  return (
    <form action={action} className="reconciliation-form">
      <input type="hidden" name="companyId" value={companyId} />
      <div className="form-grid">
        <label>Saldo final del extracto
          <select name="bankBalanceId" required defaultValue={bank[0]?.balance_id ?? ''}>
            {!bank.length ? <option value="">Sin saldo final</option> : null}
            {bank.map((item) => <option key={item.balance_id} value={item.balance_id}>
              {balanceLabel(item)}
            </option>)}
          </select>
        </label>
        <label>Saldo de libros
          <select name="booksBalanceId" required defaultValue={books[0]?.balance_id ?? ''}>
            {!books.length ? <option value="">Sin saldo de libros</option> : null}
            {books.map((item) => <option key={item.balance_id} value={item.balance_id}>
              {balanceLabel(item)}
            </option>)}
          </select>
        </label>
      </div>
      <fieldset>
        <legend>Evaluaciones incluidas</legend>
        <div className="reconciliation-checks">
          {scopedAssessments.map((item) => (
            <label key={item.assessment_id}>
              <input type="checkbox" name="assessmentIds" value={item.assessment_id}
                defaultChecked />
              <span>{item.source_name} · {item.period_start}–{item.period_end}</span>
              <span className={`outcome ${item.state === 'verified' ? '' : 'denied'}`}>
                {STATE_LABELS[item.state] ?? item.state}
              </span>
            </label>
          ))}
          {!scopedAssessments.length ? <p role="status">
            No hay evaluaciones para la cuenta y el periodo de los saldos seleccionados.
          </p> : null}
        </div>
      </fieldset>
      <p className="meta">
        Las partidas confirmadas vigentes se incorporan automaticamente. Repetir
        las mismas entradas devuelve la misma version.
      </p>
      <Feedback state={state} />
      <button type="submit" disabled={pending || !ready}>
        {pending ? 'Calculando…' : 'Calcular nueva version'}
      </button>
    </form>
  );
}

export function ItemControl({ companyId, statements, evidence }: {
  companyId: string;
  statements: BalanceReconciliationStatement[];
  evidence: BalanceEvidence[];
}) {
  const [state, action, pending] = useActionState(proposeReconcilingItemAction, INITIAL);
  const roots = [...new Map(statements.map((item) => [item.statement_root_id, item])).values()];
  const ready = roots.length > 0 && evidence.length > 0;
  return (
    <form action={action} className="reconciliation-form">
      <input type="hidden" name="companyId" value={companyId} />
      <label>Estado al que pertenece
        <select name="statementRootId" required defaultValue={roots[0]?.statement_root_id ?? ''}>
          {!roots.length ? <option value="">Calcula primero un estado</option> : null}
          {roots.map((item) => <option key={item.statement_root_id} value={item.statement_root_id}>
            {item.account_name} · {item.period_start}–{item.period_end}
          </option>)}
        </select>
      </label>
      <div className="form-grid">
        <label>Monto positivo exacto
          <input name="amount" inputMode="decimal" placeholder="125000.00"
            pattern="(?=.*[1-9])\d{1,26}(?:\.\d{1,12})?" required />
        </label>
        <label>Efecto sobre banco
          <select name="adjustmentSide" defaultValue="add_to_bank">
            <option value="add_to_bank">Sumar al saldo bancario</option>
            <option value="deduct_from_bank">Restar del saldo bancario</option>
          </select>
        </label>
        <label>Motivo documentado
          <select name="reasonCode" defaultValue="documented_timing">
            <option value="documented_timing">Diferencia temporal documentada</option>
            <option value="deposit_in_transit">Deposito en transito</option>
            <option value="outstanding_payment">Pago pendiente</option>
            <option value="bank_fee_pending">Comision bancaria pendiente</option>
            <option value="other_documented">Otro motivo documentado</option>
          </select>
        </label>
      </div>
      <label>Evidencia publicada
        <select name="evidenceSourceRecordIds" multiple required size={Math.min(5, Math.max(2, evidence.length))}>
          {evidence.map((item) => <option key={item.source_record_id} value={item.source_record_id}>
            {item.source_name} · fila {item.record_ordinal} · {item.account_name}
          </option>)}
        </select>
      </label>
      <p className="meta">Usa Ctrl/Cmd para elegir varias filas. La propuesta no entra en la ecuacion.</p>
      <Feedback state={state} />
      <button type="submit" disabled={pending || !ready}>
        {pending ? 'Proponiendo…' : 'Proponer partida'}
      </button>
    </form>
  );
}

export function ItemDecisionControl({ companyId, item, canApprove }: {
  companyId: string;
  item: ReconcilingItem;
  canApprove: boolean;
}) {
  const [state, action, pending] = useActionState(decideReconcilingItemAction, INITIAL);
  if (item.state !== 'proposed') return null;
  return (
    <form action={action} className="reconciliation-decisions">
      <input type="hidden" name="companyId" value={companyId} />
      <input type="hidden" name="itemRootId" value={item.item_root_id} />
      <button name="decision" value="confirmed" disabled={pending || !canApprove}>
        Confirmar
      </button>
      <button name="decision" value="rejected" className="secondary"
        disabled={pending || !canApprove}>Rechazar</button>
      {!canApprove ? <span className="meta">Requiere close.approve.</span> : null}
      <Feedback state={state} />
    </form>
  );
}

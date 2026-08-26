'use client';

import { useActionState, useMemo, useState } from 'react';

import {
  observeBalanceAction,
  type BalanceObservationState,
} from '@/app/actions';
import type { BalanceEvidence } from '@/lib/api';

const INITIAL: BalanceObservationState = { error: null, done: null };

const TYPES = [
  ['closing', 'Saldo final del extracto'],
  ['opening', 'Saldo inicial'],
  ['running', 'Saldo acumulado de la fila'],
  ['available', 'Saldo disponible'],
  ['ledger', 'Saldo de libros'],
] as const;

function suggestedField(
  fields: BalanceEvidence['fields'],
  names: readonly string[],
  fallback: number,
): number {
  const found = fields.find((field) => names.includes(field.label));
  return found?.index ?? fields[Math.min(fallback, Math.max(0, fields.length - 1))]?.index ?? 0;
}

function cellLabel(field: BalanceEvidence['fields'][number]): string {
  const compact = field.value.replace(/\s+/g, ' ').trim();
  const visible = compact.length > 56 ? `${compact.slice(0, 53)}…` : compact;
  return `${field.index + 1}. ${field.label}: ${visible || '(vacia)'}`;
}

export function BalanceForm({ companyId, evidence }: {
  companyId: string;
  evidence: BalanceEvidence[];
}) {
  const [state, action, pending] = useActionState(observeBalanceAction, INITIAL);
  const [recordId, setRecordId] = useState(evidence[0]?.source_record_id ?? '');
  const selected = useMemo(
    () => evidence.find((item) => item.source_record_id === recordId) ?? evidence[0],
    [evidence, recordId],
  );
  const fields = selected?.fields ?? [];
  const amountDefault = suggestedField(fields, ['amount', 'debit', 'credit'], fields.length - 1);
  const dateDefault = suggestedField(fields, ['occurred_on', 'posted_on', 'value_date'], 0);

  if (!selected) {
    return (
      <p role="status">
        No hay filas de un dataset publicado, verificado y con linaje completo.
        Publica primero la evidencia que contiene el saldo.
      </p>
    );
  }

  return (
    <form action={action} className="balance-form">
      <input type="hidden" name="companyId" value={companyId} />
      <label>
        Fila de evidencia
        <select name="sourceRecordId" value={selected.source_record_id}
          onChange={(event) => setRecordId(event.target.value)}>
          {evidence.map((item) => (
            <option key={item.source_record_id} value={item.source_record_id}>
              {item.source_name} · fila {item.record_ordinal} · {item.account_name}
            </option>
          ))}
        </select>
      </label>

      <div className="balance-evidence-summary" aria-live="polite">
        <strong>{selected.account_name}</strong>
        <span>{selected.currency_code} · {selected.source_name} · fila {selected.record_ordinal}</span>
      </div>

      <div className="form-grid">
        <label>
          Tipo de saldo
          <select name="balanceType" defaultValue="closing">
            {TYPES.map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
        <label key={`amount-${selected.source_record_id}`}>
          Columna del importe
          <select name="amountFieldIndex" defaultValue={amountDefault}>
            {fields.map((field) => (
              <option key={field.index} value={field.index}>{cellLabel(field)}</option>
            ))}
          </select>
        </label>
        <label key={`date-${selected.source_record_id}`}>
          Columna de la fecha del saldo
          <select name="asOfFieldIndex" defaultValue={dateDefault}>
            {fields.map((field) => (
              <option key={field.index} value={field.index}>{cellLabel(field)}</option>
            ))}
          </select>
        </label>
      </div>

      <p className="meta">
        El servidor relee ambas celdas con el convenio versionado; la cuenta,
        moneda, zona horaria y release no se toman del formulario.
      </p>
      {state.error ? <p className="error" role="alert">{state.error}</p> : null}
      {state.done ? <p className="notice success" role="status">{state.done}</p> : null}
      <button type="submit" disabled={pending || fields.length === 0}>
        {pending ? 'Registrando…' : 'Registrar observacion de saldo'}
      </button>
    </form>
  );
}

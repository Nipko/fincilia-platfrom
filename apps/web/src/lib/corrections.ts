import type { CorrectionTarget } from './api';

export const CORRECTION_FIELD_LABELS: Record<string, string> = {
  amount: 'Importe',
  currency: 'Moneda',
  direction: 'Direccion',
  occurred_on: 'Fecha de ocurrencia',
  posted_on: 'Fecha de asiento',
  value_date: 'Fecha valor',
  accounting_date: 'Periodo contable',
};

export const CORRECTION_STATUS_LABELS: Record<string, string> = {
  pending_review: 'Pendiente de revision',
  approved: 'Aprobada, pendiente de aplicar',
  rejected: 'Rechazada',
  applied: 'Aplicada en una version nueva',
};

export function correctionInput(target: CorrectionTarget): {
  type: 'text' | 'date';
  inputMode?: 'decimal' | 'text';
  pattern?: string;
  placeholder: string;
} {
  if (target.value_type === 'local_date') {
    return { type: 'date', placeholder: 'AAAA-MM-DD' };
  }
  if (target.value_type === 'money_decimal') {
    return {
      type: 'text', inputMode: 'decimal',
      pattern: '[0-9]{1,26}([.][0-9]{1,12})?', placeholder: '1234.56',
    };
  }
  if (target.value_type === 'currency_code') {
    return { type: 'text', inputMode: 'text', pattern: '[A-Za-z]{3}', placeholder: 'COP' };
  }
  return { type: 'text', inputMode: 'text', pattern: 'inflow|outflow', placeholder: 'inflow' };
}

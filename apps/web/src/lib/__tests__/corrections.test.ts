import { describe, expect, it } from 'vitest';

import { correctionInput } from '../corrections';

describe('correctionInput', () => {
  it('mantiene dinero como texto decimal y nunca como number', () => {
    const input = correctionInput({
      field: 'amount', value_type: 'money_decimal', current_value: '1.000000000000',
      expected_base_digest: 'a'.repeat(64),
    });
    expect(input.type).toBe('text');
    expect(input.inputMode).toBe('decimal');
    expect(input.pattern).toContain('[.]');
  });

  it('usa controles cerrados para fecha, moneda y direccion', () => {
    const target = (value_type: string) => ({
      field: 'x', value_type, current_value: null,
      expected_base_digest: 'b'.repeat(64),
    });
    expect(correctionInput(target('local_date')).type).toBe('date');
    expect(correctionInput(target('currency_code')).pattern).toBe('[A-Za-z]{3}');
    expect(correctionInput(target('enum:direction')).pattern).toBe('inflow|outflow');
  });
});

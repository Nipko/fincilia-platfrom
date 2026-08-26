import { describe, expect, it } from 'vitest';

import {
  CANDIDATE_PAGE_SIZE,
  MAX_CANDIDATE_PAGE,
  formatExactMoney,
  reconciliationReviewUrl,
  reconciliationUrl,
  selectReconciliation,
  selectReconciliationReview,
} from '../reconciliation';

describe('selectReconciliation', () => {
  const datasets = ['left', 'right', 'third'];

  it('acepta dos datasets autorizados y conserva ventana y pagina', () => {
    expect(selectReconciliation({
      izquierda: 'left', derecha: 'right', ventana: '7', pagina: '3',
    }, datasets)).toEqual({
      requested: true,
      valid: true,
      leftDatasetId: 'left',
      rightDatasetId: 'right',
      maxDays: 7,
      page: 3,
    });
  });

  it('no elige silenciosamente datasets cuando aun no se pidio comparar', () => {
    expect(selectReconciliation({}, datasets)).toEqual({
      requested: false,
      valid: false,
      leftDatasetId: '',
      rightDatasetId: '',
      maxDays: 3,
      page: 0,
    });
  });

  it.each([
    [{ izquierda: 'left', derecha: 'left' }, 'dataset repetido'],
    [{ izquierda: 'left', derecha: 'foreign' }, 'dataset ajeno'],
    [{ izquierda: ['left', 'third'], derecha: 'right' }, 'query repetida'],
    [{ izquierda: 'left', derecha: 'right', ventana: '32' }, 'ventana amplia'],
    [{ izquierda: 'left', derecha: 'right', pagina: '-1' }, 'pagina negativa'],
    [{ izquierda: 'left', derecha: 'right', pagina: String(MAX_CANDIDATE_PAGE + 1) }, 'pagina excesiva'],
  ])('rechaza %s (%s)', (query, _label) => {
    expect(selectReconciliation(query, datasets).valid).toBe(false);
  });

  it('acota el offset que se enviara a la API', () => {
    const selected = selectReconciliation({
      izquierda: 'left', derecha: 'right', pagina: String(MAX_CANDIDATE_PAGE),
    }, datasets);
    expect(selected.page * CANDIDATE_PAGE_SIZE).toBe(10_000);
  });
});

describe('reconciliationUrl', () => {
  it('conserva todo el contexto de la exploracion', () => {
    expect(reconciliationUrl('company', {
      leftDatasetId: 'left one',
      rightDatasetId: 'right/two',
      maxDays: 3,
      page: 2,
    })).toBe(
      '/empresas/company/conciliacion?' +
      'izquierda=left+one&derecha=right%2Ftwo&ventana=3&pagina=2',
    );
  });

  it('conserva el identificador estable del expediente en query y fragmento', () => {
    const candidate = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc';
    expect(reconciliationReviewUrl('company', {
      leftDatasetId: 'left', rightDatasetId: 'right', maxDays: 3, page: 0,
    }, candidate)).toBe(
      '/empresas/company/conciliacion?' +
      'izquierda=left&derecha=right&ventana=3&pagina=0&' +
      `revision=${candidate}#revision-${candidate}`,
    );
  });
});

describe('selectReconciliationReview', () => {
  it('acepta solo un UUID unico y no confunde ausencia con entrada invalida', () => {
    const candidate = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc';
    expect(selectReconciliationReview({ revision: candidate })).toEqual({
      requested: true, valid: true, candidateId: candidate,
    });
    expect(selectReconciliationReview({})).toEqual({
      requested: false, valid: false, candidateId: '',
    });
    expect(selectReconciliationReview({ revision: ['one', 'two'] }).valid)
      .toBe(false);
    expect(selectReconciliationReview({ revision: 'not-a-uuid' }).valid)
      .toBe(false);
  });
});

describe('formatExactMoney', () => {
  it('formatea la cadena decimal sin convertirla a Number', () => {
    expect(formatExactMoney('12345678901234567890123456.120000000000', 'COP'))
      .toBe('12.345.678.901.234.567.890.123.456,12 COP');
  });

  it('deja visible un valor inesperado en vez de inventar un importe', () => {
    expect(formatExactMoney('1e3', 'COP')).toBe('1e3 COP');
  });

  it('presenta diferencias negativas sin convertirlas a Number', () => {
    expect(formatExactMoney('-1234.500000000000', 'COP')).toBe('-1.234,5 COP');
  });
});

import { describe, expect, it } from 'vitest';

import { deriveAccountingFlow, type AccountingFacts } from '../accounting-flow';

const available = <T,>(value: T) => ({ state: 'available' as const, value });

function facts(overrides: Partial<AccountingFacts> = {}): AccountingFacts {
  return {
    accounts: available(1),
    sources: available(1),
    documents: available({ total: 2, raw: 2, quarantine: 0 }),
    datasets: available({ total: 2, staging: 0, validated: 0, published: 2 }),
    balances: available({ observations: 2, statements: 1, balanced: 1 }),
    close: available({ reviewReady: 1, blocked: 0 }),
    reports: available(true),
    ...overrides,
  };
}

describe('deriveAccountingFlow', () => {
  it('ordena las siete etapas sin afirmar que el cierre se ejecuta', () => {
    const stages = deriveAccountingFlow('company/synthetic', facts());

    expect(stages.map((stage) => stage.key)).toEqual([
      'setup', 'ingestion', 'canonical', 'matching', 'balances', 'close', 'reports',
    ]);
    expect(stages.find((stage) => stage.key === 'close')?.status).toBe('ready');
    expect(stages.find((stage) => stage.key === 'close')?.boundary).toMatch(/no ejecuta/i);
    expect(stages[0]?.href).toContain('company%2Fsynthetic');
  });

  it('mantiene partial y cuarentena como atención, no como éxito', () => {
    const stages = deriveAccountingFlow('company', facts({
      documents: available({ total: 1, raw: 0, quarantine: 1 }),
      datasets: available({ total: 1, staging: 1, validated: 0, published: 0 }),
    }));

    expect(stages.find((stage) => stage.key === 'ingestion')?.status).toBe('attention');
    expect(stages.find((stage) => stage.key === 'canonical')?.status).toBe('attention');
    expect(stages.find((stage) => stage.key === 'matching')?.status).toBe('blocked');
  });

  it('no convierte una restricción en conteo cero', () => {
    const stages = deriveAccountingFlow('company', facts({
      accounts: { state: 'restricted' },
      documents: { state: 'restricted' },
      reports: { state: 'restricted' },
    }));

    expect(stages.find((stage) => stage.key === 'setup')?.status).toBe('restricted');
    expect(stages.find((stage) => stage.key === 'ingestion')?.status).toBe('restricted');
    expect(stages.find((stage) => stage.key === 'reports')?.status).toBe('restricted');
  });
});

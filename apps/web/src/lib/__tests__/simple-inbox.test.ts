import { describe, expect, it } from 'vitest';

import type {
  ArtifactSummary,
  CandidateMovement,
  DatasetSummary,
  MatchReview,
  ReconciliationCandidate,
  ReconciliationRule,
  TemplateDetection,
  UnmatchedMovement,
  UploadSchedule,
} from '../api';
import { ruleConditionsForCreate } from '../api';
import {
  buildSuggestions,
  cadenceLabel,
  derivedKey,
  parseCadence,
  ruleActions,
  ruleApplications,
  ruleApprovalLabel,
  selectSimplePair,
  SIMPLE_CANDIDATE_TOLERANCE,
  summaryLine,
  templateOffer,
  unpairedMovements,
  uploadReminderText,
} from '../simple-mode';

const SOURCE_BANK = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const SOURCE_INVOICES = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
const OWNER = '11111111-1111-4111-8111-111111111111';
const OTHER = '22222222-2222-4222-8222-222222222222';

function dataset(id: string, artifact: string, publishedAt: string | null,
  state = 'published'): DatasetSummary {
  return {
    dataset_version_id: id, artifact_id: artifact, state, movement_count: 3,
    rejected_count: 0, prepared_at: '2026-02-01T00:00:00+00:00', published_at: publishedAt,
  };
}

function document(artifact: string, source: string | null): ArtifactSummary {
  return {
    artifact_id: artifact, data_source_id: source, filename: 'sintetico.csv', byte_size: 10,
    content_sha256: 'a'.repeat(64), media_type: 'text/csv', zone: 'raw', status: 'ok',
    findings: [], uploaded_at: '2026-02-01T00:00:00+00:00', already_present: false,
    promotion: null,
  };
}

function movement(id: string, overrides: Partial<CandidateMovement> = {}): CandidateMovement {
  return {
    movement_id: id, amount: '100000.000000000000', currency: 'COP', direction: 'outflow',
    description: 'Pago sintetico', reference: null, occurred_on: '2026-02-13',
    state: 'proposed', record_ordinal: 2, ...overrides,
  };
}

function free(id: string, open = false): UnmatchedMovement {
  return {
    ...movement(id), dataset_version_id: 'd', side: 'left', financial_account_id: 'f',
    has_open_candidate: open,
  };
}

function candidate(left: string, right: string,
  difference: string | null = null): ReconciliationCandidate {
  return {
    left: movement(left), right: movement(right, { direction: 'inflow' }),
    date_distance_days: 0,
    signals: [difference ? 'amount_within_tolerance' : 'exact_amount', 'same_currency'],
    explanation: difference
      ? ['Diferencia de $2.500 (posible retención o comisión)']
      : ['Mismo valor'],
    amount_difference: difference,
  };
}

function review(overrides: Partial<MatchReview> = {}): MatchReview {
  return {
    candidate_id: '55555555-5555-4555-8555-555555555555',
    left_movement_id: 'm1', right_movement_id: 'm2',
    left_dataset_id: 'l', right_dataset_id: 'r', confirmation_conflict: false,
    rule_version: 'fnc-rec-exact-v1', signals: ['exact_amount'], date_window_days: 3,
    date_distance_days: 0, proposed_by: OWNER, proposed_by_name: 'Dueña', proposed_at: '',
    status: 'open', decision: null, financial_effect: 'none',
    proves_balance_reconciliation: false, ...overrides,
  };
}

function rule(overrides: Partial<ReconciliationRule> = {}): ReconciliationRule {
  return {
    rule_id: '66666666-6666-4666-8666-666666666666', version: 1,
    conditions: {
      schema: 'fnc-rule-v1', description_contains: 'nit fnc syn nit 0091',
      financial_account_id: null, direction: 'outflow', max_amount_difference: '0',
      currency: 'COP',
    },
    description: ['La descripción contiene «nit fnc syn nit 0091»'],
    created_by: OWNER, created_by_name: 'Dueña', created_at: '',
    created_from_decision_id: null, status: 'proposed', approval: null,
    applied_count: 0, reverted_count: 0, financial_effect: 'none', ...overrides,
  };
}

describe('par de la bandeja simple', () => {
  it('elige el publicado mas reciente y el mas reciente de otra fuente', () => {
    const pair = selectSimplePair([
      dataset('old-bank', 'a1', '2026-02-01T00:00:00+00:00'),
      dataset('new-bank', 'a2', '2026-02-05T00:00:00+00:00'),
      dataset('invoices', 'a3', '2026-02-03T00:00:00+00:00'),
      dataset('draft', 'a4', null, 'validated'),
    ], [document('a1', SOURCE_BANK), document('a2', SOURCE_BANK),
      document('a3', SOURCE_INVOICES), document('a4', SOURCE_INVOICES)]);
    expect(pair).toEqual({ leftDatasetId: 'new-bank', rightDatasetId: 'invoices' });
  });

  it('sin dos fuentes publicadas no inventa un par', () => {
    expect(selectSimplePair([dataset('a', 'a1', '2026-02-01T00:00:00+00:00'),
      dataset('b', 'a2', '2026-02-02T00:00:00+00:00')],
    [document('a1', SOURCE_BANK), document('a2', SOURCE_BANK)])).toBeNull();
    expect(selectSimplePair([], [])).toBeNull();
  });
});

describe('sugerencias y pendientes', () => {
  it('solo sugiere pares libres y sin expediente abierto, con su diferencia', () => {
    const suggestions = buildSuggestions(
      [candidate('m1', 'm2'), candidate('m3', 'm4', '2500.000000000000'),
        candidate('m5', 'm6'), candidate('m1', 'm2')],
      [free('m1'), free('m2'), free('m3'), free('m4'), free('m5')],
      [review({ left_movement_id: 'm2', right_movement_id: 'm1' })],
    );
    expect(suggestions.map((item) => item.key)).toEqual(['suggestion:m3:m4']);
    expect(suggestions[0]?.title).toBe('Posible cruce con diferencia');
    expect(suggestions[0]?.explanation[0]).toContain('posible retención');
    expect(suggestions[0]?.amountDifference).toBe('2500.000000000000');
  });

  it('lo que no tiene sugerencia ni candidato abierto queda sin pareja', () => {
    const suggestions = buildSuggestions([candidate('m3', 'm4')],
      [free('m3'), free('m4'), free('m7'), free('m8', true)], []);
    expect(unpairedMovements([free('m3'), free('m4'), free('m7'), free('m8', true)],
      suggestions).map((item) => item.movement_id)).toEqual(['m7']);
  });

  it('solo las aplicaciones de regla vigentes se pueden deshacer', () => {
    const decision = {
      decision_id: 'd1', decision: 'confirmed' as const, reason_code: 'approved_rule_match',
      decided_by: OWNER, decided_by_name: 'Dueña', decided_at: '2026-02-13T00:00:00Z',
      review_mode: 'approved_rule' as const, rule_id: 'r', rule_version: 1,
    };
    const items = ruleApplications([
      review({ status: 'confirmed', decision }),
      review({ status: 'confirmed', decision: { ...decision, review_mode: 'self_reviewed' } }),
      review({ status: 'reverted', decision: { ...decision, reversal: {
        reversal_id: 'x', reason_code: 'rule_too_broad', reversed_by: OWNER, reversed_at: '',
      } } }),
    ]);
    expect(items).toHaveLength(1);
  });

  it('resume con conteos y nunca importes', () => {
    expect(summaryLine({
      period_start: '2026-11-01', period_end: '2026-11-30', eligible_movements: 9,
      matched: 4, pending: 3, to_review: 2, financial_effect: 'none',
      proves_balance_reconciliation: false, notice: '',
    })).toBe('4 conciliados, 3 pendientes, 2 por revisar');
  });
});

describe('tolerancia por defecto del modo simple', () => {
  it('es texto decimal acotado al maximo que acepta la API', () => {
    expect(typeof SIMPLE_CANDIDATE_TOLERANCE.percent).toBe('string');
    expect(typeof SIMPLE_CANDIDATE_TOLERANCE.amount).toBe('string');
    expect(Number(SIMPLE_CANDIDATE_TOLERANCE.percent)).toBeLessThanOrEqual(5);
    expect(Number(SIMPLE_CANDIDATE_TOLERANCE.amount)).toBeLessThanOrEqual(10_000_000);
    expect(SIMPLE_CANDIDATE_TOLERANCE.amount).toMatch(/^\d{1,15}(\.\d{1,12})?$/);
  });
});

describe('plantillas despues de procesar', () => {
  function detection(overrides: Partial<TemplateDetection>): TemplateDetection {
    return {
      status: 'ready', findings: [], manual_mapping_available: true,
      template: {
        template_id: 'bancolombia-cuenta-movimientos', bank: 'Bancolombia',
        calibration: 'synthetic_hypothesis', source: 'bank_template',
      },
      ...overrides,
    };
  }

  it('ofrece la plantilla bancaria con aviso de prueba', () => {
    expect(templateOffer(detection({}))).toEqual({
      kind: 'template', label: 'Usar plantilla Bancolombia',
      warning: 'Plantilla de prueba — verifica las columnas',
    });
  });

  it('DIAN y MT940 pasan con su estructura conocida, sin aviso', () => {
    const dian = templateOffer(detection({ template: {
      template_id: 'dian-ubl-invoice', calibration: 'format_specification',
      source: 'format_specification',
    } }));
    expect(dian).toEqual({
      kind: 'template', label: 'Usar estructura de factura electrónica DIAN', warning: null,
    });
    expect(templateOffer(detection({ template: {
      template_id: 'swift-mt940', source: 'format_specification',
    } }))).toMatchObject({ label: 'Usar estructura de extracto MT940', warning: null });
  });

  it('sin deteccion inequivoca cae al mapeo manual; sin extraer, espera', () => {
    expect(templateOffer(detection({ status: 'needs_review' }))).toEqual({ kind: 'manual' });
    expect(templateOffer(detection({ status: 'not_detected', template: null })))
      .toEqual({ kind: 'manual' });
    expect(templateOffer(detection({ status: 'not_extracted' }))).toEqual({ kind: 'pending' });
    expect(templateOffer(null)).toEqual({ kind: 'pending' });
  });
});

describe('reglas', () => {
  const permissions = ['movement.read', 'match.propose', 'match.confirm', 'match.reject'];

  it('en simple el autor aprueba; en estricto aprueba otra persona', () => {
    expect(ruleActions(rule(), { actorId: OWNER, permissions, profile: 'simple' }))
      .toEqual(['approve', 'retire']);
    expect(ruleActions(rule(), { actorId: OWNER, permissions, profile: 'estricto' }))
      .toEqual(['retire']);
    expect(ruleActions(rule(), { actorId: OTHER, permissions, profile: 'estricto' }))
      .toEqual(['approve', 'retire']);
  });

  it('pausa, reanuda y retira segun el estado; sin permiso no ofrece nada', () => {
    const context = { actorId: OWNER, permissions, profile: 'simple' as const };
    expect(ruleActions(rule({ status: 'active' }), context)).toEqual(['pause', 'retire']);
    expect(ruleActions(rule({ status: 'paused' }), context)).toEqual(['resume', 'retire']);
    expect(ruleActions(rule({ status: 'retired' }), context)).toEqual([]);
    expect(ruleActions(rule(), { ...context, permissions: ['movement.read'] })).toEqual([]);
  });

  it('dice honestamente si la regla fue autorrevisada', () => {
    expect(ruleApprovalLabel(rule())).toBeNull();
    expect(ruleApprovalLabel(rule({ approval: {
      approved_by: OWNER, approved_by_name: 'Dueña', review_mode: 'self_reviewed',
      approved_at: '',
    } }))).toBe('Autorrevisada por Dueña');
    expect(ruleApprovalLabel(rule({ approval: {
      approved_by: OTHER, approved_by_name: 'Contador', review_mode: 'independent',
      approved_at: '',
    } }))).toBe('Aprobada por Contador');
  });

  it('no envia el esquema: lo fija el servidor', () => {
    expect(ruleConditionsForCreate(rule().conditions)).not.toHaveProperty('schema');
  });

  it('deriva claves validas para cada paso de un mismo gesto', () => {
    expect(derivedKey('smb-0123456789abcdef', 'rule-create'))
      .toBe('smb-0123456789abcdef.rule-create');
    expect(derivedKey('x', 'y')).toBeNull();
    expect(derivedKey(`smb-${'a'.repeat(130)}`, 'z')).toBeNull();
  });
});

describe('cadencia de carga', () => {
  function schedule(overrides: Partial<UploadSchedule> = {}): UploadSchedule {
    return {
      company_id: 'c', cadence: 'monthly', can_change: true,
      current_period: {
        period_start: '2026-11-01', period_end: '2026-11-30', due_on: '2026-11-30',
        uploaded: false, reminder_state: 'due_soon',
      },
      history: [], channels: { in_app: true, external: [] }, notice: '', changed: false,
      ...overrides,
    };
  }

  it('acepta solo las tres frecuencias', () => {
    expect(parseCadence('weekly')).toBe('weekly');
    expect(parseCadence('biweekly')).toBe('biweekly');
    expect(parseCadence('daily')).toBeNull();
    expect(cadenceLabel('biweekly')).toBe('Quincenal');
    expect(cadenceLabel(null)).toBe('Sin definir');
  });

  it('el recordatorio es en la app y nunca dice que se envio un correo', () => {
    const texts = [
      uploadReminderText(schedule()),
      uploadReminderText(schedule({ cadence: null, current_period: null })),
      uploadReminderText(schedule({ current_period: {
        period_start: '2026-11-01', period_end: '2026-11-30', due_on: '2026-11-30',
        uploaded: true, reminder_state: 'received',
      } })),
    ];
    expect(texts[0]).toContain('antes del 2026-11-30');
    expect(texts[1]).toContain('dentro de Fincilia');
    expect(texts[2]).toContain('Ya recibimos');
    for (const text of texts) expect(text.toLowerCase()).not.toContain('correo');
  });
});

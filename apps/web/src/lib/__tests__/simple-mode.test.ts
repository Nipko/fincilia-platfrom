import { describe, expect, it } from 'vitest';

import type {
  AccountingPeriodClose,
  BalanceReconciliationStatement,
  DatasetSummary,
  MatchReview,
  ReconcilingItem,
} from '../api';
import {
  buildPendingInbox,
  candidateExplanation,
  closeCertificationView,
  latestClose,
  mayOfferCertification,
  operatingProfileOf,
  parseTeamSizeBand,
  reviewModeLabel,
  TEAM_SIZE_OPTIONS,
  validProfileReason,
} from '../simple-mode';

const COMPANY = '161b0037-c445-50aa-b400-72632d3f53f0';
const OWNER = '11111111-1111-4111-8111-111111111111';
const ACCOUNTANT = '22222222-2222-4222-8222-222222222222';

function close(overrides: Partial<AccountingPeriodClose> = {}): AccountingPeriodClose {
  return {
    close_id: '33333333-3333-4333-8333-333333333333',
    period_start: '2026-09-01',
    period_end: '2026-09-30',
    version: 1,
    packet_id: '44444444-4444-4444-8444-444444444444',
    observed_manifest_digest: 'a'.repeat(64),
    snapshot_schema_version: 'accounting-close-v1',
    snapshot: {} as AccountingPeriodClose['snapshot'],
    snapshot_digest: 'b'.repeat(64),
    closed_by: OWNER,
    closer_name: 'Dueña Sintetica',
    closed_at: '2026-10-02T10:00:00+00:00',
    status: 'closed',
    reopen_request: null,
    replayed: false,
    financial_effect: 'period_state_only',
    certifies_financial_statements: false,
    ...overrides,
  };
}

function review(overrides: Partial<MatchReview> = {}): MatchReview {
  return {
    candidate_id: '55555555-5555-4555-8555-555555555555',
    left_movement_id: '66666666-6666-4666-8666-666666666666',
    right_movement_id: '77777777-7777-4777-8777-777777777777',
    left_dataset_id: '88888888-8888-4888-8888-888888888888',
    right_dataset_id: '99999999-9999-4999-8999-999999999999',
    confirmation_conflict: false,
    rule_version: 'match-v1',
    signals: ['exact_amount', 'same_currency'],
    date_window_days: 3,
    date_distance_days: 1,
    proposed_by: OWNER,
    proposed_by_name: 'Dueña Sintetica',
    proposed_at: '2026-10-01T10:00:00+00:00',
    status: 'open',
    decision: null,
    financial_effect: 'none',
    proves_balance_reconciliation: false,
    ...overrides,
  };
}

describe('perfil operativo', () => {
  it('ofrece exactamente las dos bandas del alta con su perfil sugerido', () => {
    expect(TEAM_SIZE_OPTIONS.map((option) => [option.band, option.profile]))
      .toEqual([['1-2', 'simple'], ['3+', 'estricto']]);
    expect(parseTeamSizeBand('1-2')).toBe('1-2');
    expect(parseTeamSizeBand('3+')).toBe('3+');
    expect(parseTeamSizeBand('simple')).toBeNull();
    expect(parseTeamSizeBand(null)).toBeNull();
  });

  it('trata un perfil ausente o desconocido como estricto', () => {
    expect(operatingProfileOf({ operating_profile: 'simple' })).toBe('simple');
    expect(operatingProfileOf({})).toBe('estricto');
    expect(operatingProfileOf({ operating_profile: 'otro' })).toBe('estricto');
  });

  it('valida el motivo del cambio', () => {
    expect(validProfileReason('corto')).toBe(false);
    expect(validProfileReason('  Ahora somos tres personas.  ')).toBe(true);
    expect(validProfileReason(`Motivo con\u0007control`)).toBe(false);
    expect(validProfileReason('x'.repeat(501))).toBe(false);
  });
});

describe('modo de revision', () => {
  it('usa lenguaje llano y nunca inventa un modo', () => {
    expect(reviewModeLabel('independent')).toBe('Revisado por otra persona');
    expect(reviewModeLabel('self_reviewed')).toBe('Autorrevisado');
    expect(reviewModeLabel('approved_rule')).toBe('Regla aprobada');
    expect(reviewModeLabel(undefined)).toBeNull();
    expect(reviewModeLabel('otra_cosa')).toBeNull();
  });
});

describe('certificacion del cierre', () => {
  it('distingue autorrevisado de certificado', () => {
    expect(closeCertificationView(close({ certification: 'self_reviewed' })).label)
      .toBe('Cerrado — autorrevisado');
    expect(closeCertificationView(close({
      certification: 'certified',
      certification_record: {
        certification_id: 'c', certified_by: ACCOUNTANT,
        certifier_name: 'Contador Sintetico', certified_at: '2026-10-05T10:00:00+00:00',
      },
    })).label).toBe('Cerrado — certificado por Contador Sintetico');
  });

  it('trata un cierre previo a ADR-039 como certificado por otra persona', () => {
    expect(closeCertificationView(close()).state).toBe('certified');
  });

  it('solo ofrece certificar a una segunda persona con permiso', () => {
    const selfReviewed = close({ certification: 'self_reviewed' });
    expect(mayOfferCertification(selfReviewed, ACCOUNTANT, ['close.approve'])).toBe(true);
    expect(mayOfferCertification(selfReviewed, OWNER, ['close.approve'])).toBe(false);
    expect(mayOfferCertification(selfReviewed, ACCOUNTANT, ['report.read'])).toBe(false);
    expect(mayOfferCertification(close({ certification: 'certified' }), ACCOUNTANT,
      ['close.approve'])).toBe(false);
    expect(mayOfferCertification(close({ certification: 'self_reviewed', status: 'reopened' }),
      ACCOUNTANT, ['close.approve'])).toBe(false);
  });

  it('elige el cierre vigente mas reciente', () => {
    const older = close({ close_id: 'a', period_end: '2026-08-31' });
    const reopened = close({ close_id: 'b', status: 'reopened' });
    const current = close({ close_id: 'c', version: 2 });
    expect(latestClose([older, reopened, current])?.close_id).toBe('c');
    expect(latestClose([])).toBeNull();
  });
});

describe('bandeja de pendientes', () => {
  it('lista solo lo que no cuadra o espera decision', () => {
    const datasets = [
      { dataset_version_id: 'd1', artifact_id: 'a1', state: 'validated', movement_count: 4,
        rejected_count: 0, prepared_at: '', published_at: null },
      { dataset_version_id: 'd2', artifact_id: 'a2', state: 'published', movement_count: 9,
        rejected_count: 0, prepared_at: '', published_at: '' },
    ] as DatasetSummary[];
    const items = [
      { item_decision_id: 'i1', state: 'proposed', amount: '10.00', currency_code: 'COP',
        adjustment_side: 'add_to_bank' },
      { item_decision_id: 'i2', state: 'confirmed', amount: '5.00', currency_code: 'COP',
        adjustment_side: 'add_to_bank' },
    ] as ReconcilingItem[];
    const statements = [
      { statement_id: 's1', statement_root_id: 'r1', version: 1, state: 'review_required',
        account_name: 'Banco', unexplained_difference: '3.00', currency_code: 'COP' },
      { statement_id: 's2', statement_root_id: 'r1', version: 2, state: 'balanced',
        account_name: 'Banco', unexplained_difference: '0.00', currency_code: 'COP' },
    ] as BalanceReconciliationStatement[];

    const entries = buildPendingInbox(COMPANY, {
      reviews: [review(), review({ candidate_id: 'cerrado', status: 'confirmed' })],
      datasets, items, statements,
    });

    expect(entries.map((entry) => entry.kind)).toEqual(['candidate', 'dataset', 'item']);
    expect(entries[0]?.href).toContain(`#revision-${review().candidate_id}`);
  });

  it('muestra la explicacion de la API y el modo si llegan', () => {
    const [entry] = buildPendingInbox(COMPANY, {
      reviews: [review({ explanation: ['Mismo NIT del pagador.'], review_mode: 'approved_rule' })],
      datasets: null, items: null, statements: null,
    });
    expect(entry?.explanation).toEqual(['Mismo NIT del pagador.']);
    expect(entry?.reviewMode).toBe('approved_rule');
  });

  it('tolera la ausencia de explicacion describiendo las senales', () => {
    expect(candidateExplanation(review())).toEqual([
      'El monto coincide exactamente.', 'La moneda es la misma.',
    ]);
  });
});

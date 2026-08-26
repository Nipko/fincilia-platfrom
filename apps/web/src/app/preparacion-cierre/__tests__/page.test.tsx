import { render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('server-only', () => ({}));

const mocks = vi.hoisted(() => ({
  fetchMe: vi.fn(), loadCloseReadinessCenter: vi.fn(),
  loadCloseReviewCenter: vi.fn(), readSession: vi.fn(),
  redirect: vi.fn((): never => { throw new Error('NEXT_REDIRECT'); }),
}));

vi.mock('next/navigation', () => ({ redirect: mocks.redirect }));
vi.mock('@/lib/session', () => ({ readSession: mocks.readSession }));
vi.mock('@/app/empresas/sign-out', () => ({ SignOut: () => <button>Salir</button> }));
vi.mock('@/lib/api', async (importOriginal) => ({
  ...await importOriginal<typeof import('@/lib/api')>(),
  fetchMe: mocks.fetchMe,
}));
vi.mock('@/lib/close-readiness', async (importOriginal) => ({
  ...await importOriginal<typeof import('@/lib/close-readiness')>(),
  loadCloseReadinessCenter: mocks.loadCloseReadinessCenter,
}));
vi.mock('@/lib/close-review', async (importOriginal) => ({
  ...await importOriginal<typeof import('@/lib/close-review')>(),
  loadCloseReviewCenter: mocks.loadCloseReviewCenter,
}));

import CloseReadinessPage from '../page';

const COMPANY = '161b0037-c445-50aa-b400-72632d3f53f0';
const STATEMENT = '61111111-1111-4111-8111-111111111111';
const DIGEST = 'a'.repeat(64);

describe('CloseReadinessPage lineage drill-down', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.readSession.mockResolvedValue({ token: 'synthetic-token' });
    const company = {
      company_id: COMPANY, legal_name: 'Panaderia La Espiga SAS',
      country_code: 'CO', status: 'active', roles: ['owner'],
    };
    mocks.fetchMe.mockResolvedValue({
      subject_id: 'subject-synthetic', display_name: 'Fundador',
      session_expires_at: 2_000_000_000, companies: [company],
    });
    mocks.loadCloseReviewCenter.mockResolvedValue([{
      company, access: 'available', permissions: ['report.read'],
      reviewers: [], packets: [],
    }]);
    mocks.loadCloseReadinessCenter.mockResolvedValue([{
      company, access: 'available',
      statementLineages: {
        [STATEMENT]: {
          access: 'available', result: {
            statement_id: STATEMENT, lineage_state: 'complete', complete: true,
            notice: 'digest_only_lineage; no values or close authority',
            inputs: [{
              node_type: 'financial_fact_field',
              entity_ref: '41111111-1111-4111-8111-111111111111',
              field_name: 'amount', value_digest: DIGEST,
              operation: 'decided_using',
              processing_run_id: '71111111-1111-4111-8111-111111111111',
              engine_release_id: '81111111-1111-4111-8111-111111111111',
              canonical_schema_version: '0.1.0',
            }],
          },
        },
      },
      result: {
        mode: 'diagnostic_only', close_ready: false, can_execute_close: false,
        period_count: 1, blocked_period_count: 0, review_ready_period_count: 1,
        source_count: 1, limit: 12, notice: 'diagnostic_only', items: [{
          period_start: '2026-07-01', period_end: '2026-07-31',
          status: 'ready_for_review', close_ready: false, can_execute_close: false,
          source_count: 1, selected_dataset_count: 1, expected_account_count: 1,
          missing_account_assignment_count: 0, controls: [], blockers: [], sources: [],
          account_reconciliations: [{
            financial_account_id: 'account-synthetic', account_name: 'Cuenta demo',
            source_count: 1, assessment_count: 1, statement_root_id: 'root-synthetic',
            statement_id: STATEMENT, statement_version: 1, statement_state: 'balanced',
            statement_lineage_state: 'complete', coverage_state: 'covered',
          }],
        }],
      },
    }]);
  });

  it('explica insumos por huella sin presentar valores ni autoridad de cierre', async () => {
    render(await CloseReadinessPage({ searchParams: Promise.resolve({ empresa: COMPANY }) }));
    const disclosure = screen.getByText('Ver trazabilidad (1 insumo(s))').closest('details');
    expect(disclosure).not.toBeNull();
    expect(within(disclosure as HTMLElement).getByText('Hecho financiero'))
      .toBeInTheDocument();
    expect(within(disclosure as HTMLElement).getByText(DIGEST)).toBeInTheDocument();
    expect(within(disclosure as HTMLElement).getByText(/no contiene importes/i))
      .toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /cerrar|certificar/i }))
      .not.toBeInTheDocument();
  });

  it('presenta el expediente digest-only sin confundirlo con un cierre', async () => {
    const company = (await mocks.fetchMe()).companies[0];
    mocks.loadCloseReviewCenter.mockResolvedValue([{
      company, access: 'available', permissions: ['report.read', 'close.approve'],
      reviewers: [], packets: [{
        packet_id: '91111111-1111-4111-8111-111111111111',
        period_start: '2026-07-01', period_end: '2026-07-31', version: 2,
        manifest_schema_version: 'close-evidence-v1',
        manifest: {
          schema_version: 'close-evidence-v1', diagnostic_status: 'ready_for_review',
          controls: [{ code: 'complete_lineage', state: 'pass', count: 0 }],
          sources: [], accounts: [],
        },
        manifest_digest: DIGEST, diagnostic_status: 'ready_for_review',
        prepared_by: '21111111-1111-4111-8111-111111111111',
        preparer_name: 'Ana Preparadora',
        assigned_reviewer_id: 'subject-synthetic', reviewer_name: 'Fundador',
        prepared_at: '2026-08-26T12:00:00+00:00', decision_id: null,
        decision: null, reason_code: null, decided_by: null, decider_name: null,
        decided_at: null, reviewer_eligible: true, status: 'pending_review',
        replayed: false, financial_effect: 'none', certifies_close: false,
        can_execute_close: false,
      }],
    }]);
    render(await CloseReadinessPage({ searchParams: Promise.resolve({ empresa: COMPANY }) }));
    expect(screen.getByText('Version 2')).toBeInTheDocument();
    expect(screen.getAllByText(DIGEST)).toHaveLength(2);
    expect(screen.getByRole('button', { name: 'Marcar evidencia revisada' }))
      .toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /cerrar|certificar/i }))
      .not.toBeInTheDocument();
  });
});

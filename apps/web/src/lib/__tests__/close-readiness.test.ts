import { describe, expect, it, vi } from 'vitest';

vi.mock('server-only', () => ({}));

import {
  ApiError,
  type CloseReadinessResult,
  type CompanySummary,
} from '../api';
import {
  aggregateCloseReadinessCounts,
  availableClosePeriods,
  filterCloseReadinessPeriod,
  formatClosePeriod,
  loadCloseReadinessCompany,
  selectCloseReadinessCompanies,
  selectClosePeriod,
} from '../close-readiness';

const COMPANY: CompanySummary = {
  company_id: 'company-synthetic-a',
  legal_name: 'Empresa Sintetica A',
  country_code: 'CO',
  status: 'active',
  roles: ['reviewer'],
};

const RESULT: CloseReadinessResult = {
  mode: 'diagnostic_only',
  close_ready: false,
  can_execute_close: false,
  period_count: 1,
  blocked_period_count: 1,
  review_ready_period_count: 0,
  source_count: 2,
  limit: 12,
  notice: 'diagnostic_only',
  items: [{
    period_start: '2026-07-01',
    period_end: '2026-07-31',
    status: 'blocked',
    close_ready: false,
    can_execute_close: false,
    source_count: 2,
    selected_dataset_count: 1,
    expected_account_count: 1,
    missing_account_assignment_count: 0,
    controls: [
      { code: 'reconciliation_reviews', state: 'blocked', count: 3, detail: 'Abiertas' },
      { code: 'quality_alerts', state: 'blocked', count: 2, detail: 'Altas' },
      { code: 'pending_corrections', state: 'blocked', count: 1, detail: 'Pendientes' },
      { code: 'account_balances', state: 'unavailable', count: 1, detail: 'Ausente' },
    ],
    blockers: [
      { code: 'account_balances', count: 1, detail: 'Ausente' },
      { code: 'product_close', count: 1, detail: 'Deshabilitado' },
    ],
    sources: [],
    account_reconciliations: [],
  }],
};

function client(permissions = ['report.read']) {
  return {
    fetchCompany: vi.fn().mockResolvedValue({
      ...COMPANY,
      firm_id: 'firm-synthetic',
      engagement_id: 'engagement-synthetic',
      authorization_version: 1,
      permissions,
    }),
    fetchCloseReadiness: vi.fn().mockResolvedValue(RESULT),
    fetchStatementLineage: vi.fn().mockResolvedValue({
      statement_id: 'statement-synthetic',
      lineage_state: 'complete',
      complete: true,
      inputs: [],
      notice: 'digest_only_lineage; no values or close authority',
    }),
  };
}

describe('preparacion diagnostica de cierre', () => {
  it('solo selecciona empresas presentes en la sesion', () => {
    expect(selectCloseReadinessCompanies([COMPANY], COMPANY.company_id)).toEqual([COMPANY]);
    expect(selectCloseReadinessCompanies([COMPANY], 'company-foreign')).toEqual([COMPANY]);
    expect(selectCloseReadinessCompanies([COMPANY], ['company-synthetic-a']))
      .toEqual([COMPANY]);
  });

  it('no consulta el diagnostico sin report.read', async () => {
    const api = client([]);
    await expect(loadCloseReadinessCompany('token', COMPANY, api))
      .resolves.toMatchObject({ access: 'restricted', result: null });
    expect(api.fetchCloseReadiness).not.toHaveBeenCalled();
  });

  it('distingue revocacion, indisponibilidad y sesion expirada', async () => {
    const revoked = client();
    revoked.fetchCompany.mockRejectedValue(new ApiError(404, 'hidden'));
    await expect(loadCloseReadinessCompany('token', COMPANY, revoked))
      .resolves.toMatchObject({ access: 'revoked', result: null });

    const unavailable = client();
    unavailable.fetchCloseReadiness.mockRejectedValue(new ApiError(503, 'down'));
    await expect(loadCloseReadinessCompany('token', COMPANY, unavailable))
      .resolves.toMatchObject({ access: 'unavailable', result: null });

    const expired = client();
    expired.fetchCloseReadiness.mockRejectedValue(new ApiError(401, 'expired'));
    await expect(loadCloseReadinessCompany('token', COMPANY, expired))
      .rejects.toMatchObject({ status: 401 });
  });

  it('agrega solo conteos de trabajo y conserva el cierre denegado', async () => {
    const snapshot = await loadCloseReadinessCompany('token', COMPANY, client());
    expect(snapshot.result?.close_ready).toBe(false);
    expect(snapshot.result?.can_execute_close).toBe(false);
    const totals = aggregateCloseReadinessCounts([snapshot]);
    expect(totals).toEqual({
      periods: 1,
      blockedPeriods: 1,
      sources: 2,
      reviewReadyPeriods: 0,
      openReviews: 3,
      highAlerts: 2,
      pendingCorrections: 1,
    });
    expect(JSON.stringify(totals)).not.toMatch(/amount|balance|currency|close_ready/i);
  });

  it('distingue evidencia lista para revision de un cierre habilitado', () => {
    const ready: CloseReadinessResult = {
      ...RESULT,
      blocked_period_count: 0,
      review_ready_period_count: 1,
      items: RESULT.items.map((period) => ({
        ...period,
        status: 'ready_for_review',
        blockers: [],
      })),
    };
    const totals = aggregateCloseReadinessCounts([{
      company: COMPANY, access: 'available', result: ready, statementLineages: {},
    }]);

    expect(totals.reviewReadyPeriods).toBe(1);
    expect(totals.blockedPeriods).toBe(0);
    expect(ready.close_ready).toBe(false);
    expect(ready.can_execute_close).toBe(false);
  });

  it('carga el drill-down solo con movement.read y aisla fallos por statement', async () => {
    const statementResult: CloseReadinessResult = {
      ...RESULT,
      items: RESULT.items.map((period) => ({
        ...period,
        account_reconciliations: [{
          financial_account_id: 'account-synthetic',
          account_name: 'Cuenta sintetica', source_count: 1, assessment_count: 1,
          statement_root_id: 'root-synthetic', statement_id: 'statement-synthetic',
          statement_version: 1, statement_state: 'balanced',
          statement_lineage_state: 'complete', coverage_state: 'covered',
        }],
      })),
    };
    const allowed = client(['report.read', 'movement.read']);
    allowed.fetchCloseReadiness.mockResolvedValue(statementResult);
    const snapshot = await loadCloseReadinessCompany('token', COMPANY, allowed);
    expect(snapshot.statementLineages['statement-synthetic']).toMatchObject({
      access: 'available', result: { complete: true },
    });
    expect(allowed.fetchStatementLineage).toHaveBeenCalledOnce();

    const restricted = client(['report.read']);
    restricted.fetchCloseReadiness.mockResolvedValue(statementResult);
    const restrictedSnapshot = await loadCloseReadinessCompany(
      'token', COMPANY, restricted);
    expect(restrictedSnapshot.statementLineages['statement-synthetic'])
      .toEqual({ access: 'restricted', result: null });
    expect(restricted.fetchStatementLineage).not.toHaveBeenCalled();

    const unavailable = client(['report.read', 'movement.read']);
    unavailable.fetchCloseReadiness.mockResolvedValue(statementResult);
    unavailable.fetchStatementLineage.mockRejectedValue(new ApiError(503, 'down'));
    await expect(loadCloseReadinessCompany('token', COMPANY, unavailable))
      .resolves.toMatchObject({
        access: 'available',
        statementLineages: {
          'statement-synthetic': { access: 'unavailable', result: null },
        },
      });
  });

  it('formatea periodos sin reinterpretar la zona horaria', () => {
    expect(formatClosePeriod('2026-07-01', '2026-07-31'))
      .toMatch(/1.*jul.*2026.*31.*jul.*2026/i);
  });

  it('filtra solo periodos descubiertos en respuestas autorizadas', async () => {
    const snapshot = await loadCloseReadinessCompany('token', COMPANY, client());
    const available = availableClosePeriods([snapshot]);
    expect(available).toEqual([{
      key: '2026-07-01:2026-07-31', start: '2026-07-01', end: '2026-07-31',
    }]);
    expect(selectClosePeriod(available, 'foreign:period')).toBe('todos');
    const selected = selectClosePeriod(available, available[0]?.key);
    const filtered = filterCloseReadinessPeriod([snapshot], selected);
    expect(filtered[0]?.result).toMatchObject({
      period_count: 1, blocked_period_count: 1, source_count: 2,
    });
    expect(filterCloseReadinessPeriod([snapshot], '2025-01-01:2025-01-31')[0]
      ?.result).toMatchObject({ period_count: 0, source_count: 0 });
  });
});

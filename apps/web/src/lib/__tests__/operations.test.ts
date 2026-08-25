import { describe, expect, it, vi } from 'vitest';

vi.mock('server-only', () => ({}));

import {
  ApiError,
  type CompanySummary,
  type OperationalPeriod,
  type OperationalPeriodPage,
} from '../api';
import {
  aggregateOperationalSummary,
  loadOperationsCompanySnapshot,
  operationsHref,
  parseOperationsFilter,
  selectCompanies,
  sortedOperationalEntries,
} from '../operations';

const COMPANY: CompanySummary = {
  company_id: 'company-synthetic-a',
  legal_name: 'Empresa Sintetica A',
  country_code: 'CO',
  status: 'active',
  roles: ['owner'],
};

function period(
  expectationId: string,
  state: OperationalPeriod['reminder_state'],
  dueOn: string,
): OperationalPeriod {
  return {
    expectation_id: expectationId,
    data_source_id: `source-${expectationId}`,
    source_name: `Fuente ${expectationId}`,
    period_start: '2026-08-01',
    period_end: '2026-08-31',
    due_on: dueOn,
    late_after: '2026-09-03',
    stored_state: 'pending',
    satisfied_at: null,
    waived_reason: null,
    responsible_subject_id: 'subject-ana',
    responsible_name: 'Ana Preparadora',
    responsible_eligible: true,
    assigned_to_me: false,
    timezone: 'America/Bogota',
    local_as_of: '2026-08-24',
    reminder_state: state,
    days_late: state === 'overdue' ? 3 : 0,
    days_until_due: state === 'overdue' ? -6 : 2,
  };
}

function page(items: OperationalPeriod[]): OperationalPeriodPage {
  return {
    evaluated_at: '2026-08-25T00:30:00Z',
    local_as_of_dates: ['2026-08-24'],
    filter: 'attention',
    limit: 50,
    has_more: false,
    next_cursor: null,
    summary: {
      period_count: items.length,
      source_count: items.length,
      overdue: items.filter((item) => item.reminder_state === 'overdue').length,
      in_grace: items.filter((item) => item.reminder_state === 'in_grace').length,
      due_today: items.filter((item) => item.reminder_state === 'due_today').length,
      due_soon: items.filter((item) => item.reminder_state === 'due_soon').length,
      upcoming: items.filter((item) => item.reminder_state === 'upcoming').length,
      satisfied: items.filter((item) => item.reminder_state === 'satisfied').length,
      waived: items.filter((item) => item.reminder_state === 'waived').length,
      filtered_total: items.length,
      oldest_due_on: items[0]?.due_on ?? null,
      newest_due_on: items.at(-1)?.due_on ?? null,
    },
    items,
    notice: 'in_app_projection_only',
  };
}

function client(permissions = ['data_source.manage']) {
  return {
    fetchCompany: vi.fn().mockResolvedValue({
      ...COMPANY,
      firm_id: 'firm-synthetic',
      engagement_id: 'engagement-synthetic',
      authorization_version: 4,
      permissions,
    }),
    fetchOperationalPeriods: vi.fn().mockResolvedValue(
      page([period('due', 'due_soon', '2026-08-26')]),
    ),
  };
}

describe('centro operativo multiempresa', () => {
  it('normaliza filtros y seleccion de empresa con vocabulario cerrado', () => {
    expect(parseOperationsFilter('vencidos')).toBe('vencidos');
    expect(parseOperationsFilter('fraude')).toBe('atencion');
    expect(parseOperationsFilter(['todos'])).toBe('atencion');
    expect(selectCompanies([COMPANY], COMPANY.company_id)).toEqual([COMPANY]);
    expect(selectCompanies([COMPANY], 'company-foreign')).toEqual([COMPANY]);
    expect(operationsHref('hoy', COMPANY.company_id)).toBe(
      '/recordatorios?estado=hoy&empresa=company-synthetic-a',
    );
  });

  it('no consulta periodos sin permiso ni convierte restriccion en cero', async () => {
    const api = client([]);
    const snapshot = await loadOperationsCompanySnapshot(
      'token-synthetic', COMPANY, 'attention', api,
    );
    expect(snapshot).toMatchObject({ access: 'restricted', page: null });
    expect(api.fetchOperationalPeriods).not.toHaveBeenCalled();
  });

  it('conserva revocacion fallo parcial y expiracion como estados distintos', async () => {
    const revoked = client();
    revoked.fetchCompany.mockRejectedValue(new ApiError(404, 'hidden'));
    await expect(loadOperationsCompanySnapshot(
      'token-synthetic', COMPANY, 'attention', revoked,
    )).resolves.toMatchObject({ access: 'revoked', page: null });

    const partial = client();
    partial.fetchOperationalPeriods.mockRejectedValue(new ApiError(503, 'down'));
    await expect(loadOperationsCompanySnapshot(
      'token-synthetic', COMPANY, 'attention', partial,
    )).resolves.toMatchObject({ access: 'unavailable', page: null });

    const expired = client();
    expired.fetchOperationalPeriods.mockRejectedValue(new ApiError(401, 'expired'));
    await expect(loadOperationsCompanySnapshot(
      'token-synthetic', COMPANY, 'attention', expired,
    )).rejects.toMatchObject({ status: 401 });
  });

  it('prioriza atraso sobre fecha y suma solo conteos operativos disponibles', () => {
    const another = { ...COMPANY, company_id: 'company-b', legal_name: 'Empresa B' };
    const snapshots = [
      { company: COMPANY, access: 'available' as const,
        page: page([period('soon', 'due_soon', '2026-08-25')]) },
      { company: another, access: 'available' as const,
        page: page([period('late', 'overdue', '2026-08-30')]) },
      { company: { ...COMPANY, company_id: 'company-c' },
        access: 'unavailable' as const, page: null },
    ];
    const entries = sortedOperationalEntries(snapshots);
    expect(entries.map((entry) => entry.period.expectation_id)).toEqual([
      'late', 'soon',
    ]);
    const summary = aggregateOperationalSummary(snapshots);
    expect(summary).toMatchObject({ period_count: 2, overdue: 1, due_soon: 1 });
    expect(JSON.stringify({ entries, summary })).not.toMatch(/amount|balance|currency/i);
  });
});

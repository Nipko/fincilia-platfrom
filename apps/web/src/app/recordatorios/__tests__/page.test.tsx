import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('server-only', () => ({}));

const mocks = vi.hoisted(() => {
  class ApiError extends Error {
    readonly status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  }
  return {
    ApiError,
    fetchMe: vi.fn(),
    fetchNotificationPreference: vi.fn(),
    fetchNotificationDeliveries: vi.fn(),
    loadOperationsCenter: vi.fn(),
    readSession: vi.fn(),
    redirect: vi.fn((): never => { throw new Error('NEXT_REDIRECT'); }),
  };
});

vi.mock('next/navigation', () => ({ redirect: mocks.redirect }));
vi.mock('@/lib/session', () => ({ readSession: mocks.readSession }));
vi.mock('@/lib/api', () => ({
  ApiError: mocks.ApiError,
  fetchMe: mocks.fetchMe,
  fetchNotificationPreference: mocks.fetchNotificationPreference,
  fetchNotificationDeliveries: mocks.fetchNotificationDeliveries,
}));
vi.mock('@/lib/operations', () => ({
  loadOperationsCenter: mocks.loadOperationsCenter,
  parseOperationsFilter: (value: unknown) => value === 'todos' ? 'todos' : 'atencion',
  selectCompanies: (companies: unknown[]) => companies,
  operationsHref: (filter: string) => `/recordatorios?estado=${filter}`,
  sortedOperationalEntries: (snapshots: Array<{ company: unknown; page: { items: unknown[] } | null }>) =>
    snapshots.flatMap((snapshot) => snapshot.page?.items.map((period) => ({
      company: snapshot.company,
      period,
    })) ?? []),
  aggregateOperationalSummary: (snapshots: Array<{ page: { summary: unknown } | null }>) =>
    snapshots.find((snapshot) => snapshot.page)?.page?.summary ?? {
      period_count: 0, source_count: 0, overdue: 0, in_grace: 0,
      due_today: 0, due_soon: 0, upcoming: 0, satisfied: 0, waived: 0,
      filtered_total: 0, oldest_due_on: null, newest_due_on: null,
    },
}));
vi.mock('../notification-controls', () => ({
  NotificationControls: () => <section>Avisos por correo</section>,
}));

import OperationsPage from '../page';

const company = {
  company_id: 'company-synthetic-a',
  legal_name: 'Empresa Sintetica A',
  country_code: 'CO',
  status: 'active',
  roles: ['owner'],
};

const reminder = {
  expectation_id: 'expectation-synthetic-a',
  data_source_id: 'source-synthetic-a',
  source_name: 'Banco sintetico',
  period_start: '2026-08-01',
  period_end: '2026-08-31',
  due_on: '2026-09-01',
  late_after: '2026-09-04',
  stored_state: 'pending',
  satisfied_at: null,
  waived_reason: null,
  responsible_subject_id: 'subject-sofia',
  responsible_name: 'Sofia Propietaria',
  responsible_eligible: true,
  assigned_to_me: true,
  timezone: 'America/Bogota',
  local_as_of: '2026-08-24',
  reminder_state: 'due_soon',
  days_late: 0,
  days_until_due: 3,
};

const summary = {
  period_count: 1,
  source_count: 1,
  overdue: 0,
  in_grace: 0,
  due_today: 0,
  due_soon: 1,
  upcoming: 0,
  satisfied: 0,
  waived: 0,
  filtered_total: 1,
  oldest_due_on: reminder.due_on,
  newest_due_on: reminder.due_on,
};

describe('OperationsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.readSession.mockResolvedValue({ token: 'token-synthetic' });
    mocks.fetchMe.mockResolvedValue({
      display_name: 'Sofia Propietaria', companies: [company],
    });
    mocks.fetchNotificationPreference.mockResolvedValue({
      preference_id: null, channel: 'email', purpose_code: 'operational_reminder',
      enabled: false, locale: 'es-CO', timezone: 'America/Bogota',
      quiet_from: '20:00', quiet_until: '07:00', updated_at: null,
      destination_state: 'provider_configuration_pending',
    });
    mocks.fetchNotificationDeliveries.mockResolvedValue([]);
  });

  it('muestra prioridad responsable fechas y accion exacta', async () => {
    mocks.loadOperationsCenter.mockResolvedValue([{
      company,
      access: 'available',
      page: {
        evaluated_at: '2026-08-25T00:30:00Z',
        local_as_of_dates: ['2026-08-24'],
        has_more: false, items: [reminder], summary,
      },
    }]);
    render(await OperationsPage({ searchParams: Promise.resolve({}) }));

    expect(screen.getByRole('heading', {
      name: 'Centro de ciclos y recordatorios',
    })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Banco sintetico' }))
      .toBeInTheDocument();
    expect(screen.getByText('Sofia Propietaria · asignado a ti'))
      .toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Abrir fuente' })).toHaveAttribute(
      'href',
      '/empresas/company-synthetic-a/fuentes/source-synthetic-a#ciclo-esperado',
    );
    expect(screen.getByText(/no prueban que se envio correo/i)).toBeInTheDocument();
  });

  it('declara vista parcial y no certifica un vacio', async () => {
    mocks.loadOperationsCenter.mockResolvedValue([{
      company, access: 'unavailable', page: null,
    }]);
    render(await OperationsPage({ searchParams: Promise.resolve({}) }));

    expect(screen.getByText('Vista parcial.')).toBeInTheDocument();
    expect(screen.getByText(/no se contabilizan como cero pendientes/i))
      .toBeInTheDocument();
    expect(screen.getByText(/un vacio operativo no certifica/i))
      .toBeInTheDocument();
  });
});

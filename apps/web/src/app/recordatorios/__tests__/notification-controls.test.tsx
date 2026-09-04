import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('@/app/actions', () => ({
  syncNotificationRemindersAction: vi.fn(),
  updateNotificationPreferenceAction: vi.fn(),
}));

import { NotificationControls } from '../notification-controls';

describe('NotificationControls', () => {
  it('distingue intención, supresión y entrega externa', () => {
    render(<NotificationControls companyId="company-1" preference={{
      preference_id: 'preference-1', channel: 'email',
      purpose_code: 'operational_reminder', enabled: true, locale: 'es-CO',
      timezone: 'America/Bogota', quiet_from: '20:00', quiet_until: '07:00',
      updated_at: '2026-09-01T12:00:00Z',
      destination_state: 'provider_configuration_pending',
    }} deliveries={[{
      delivery_id: 'delivery-1', template_code: 'period_due_today',
      context: { period_label: '2026-08 / 2026-08', due_on: '2026-09-05',
        action_url: '/recordatorios?empresa=company-1' },
      status: 'suppressed', suppression_reason: 'adapter_unconfigured',
      attempt_count: 0, created_at: '2026-09-04T12:00:00Z',
      updated_at: '2026-09-04T12:00:00Z',
    }]} />);

    expect(screen.getByText('Entrega externa desactivada')).toBeInTheDocument();
    expect(screen.getByText('Suprimido')).toBeInTheDocument();
    expect(screen.getByText('Proveedor de correo sin configurar')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Abrir ciclo' })).toHaveAttribute(
      'href', '/recordatorios?empresa=company-1');
    expect(screen.getByText('1', { selector: 'dd' })).toBeInTheDocument();
  });
});

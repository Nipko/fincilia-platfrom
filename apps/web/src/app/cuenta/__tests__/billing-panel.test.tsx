import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('@/app/actions', () => ({
  selectEvaluationPlanAction: vi.fn(),
}));

import { BillingPanel } from '../billing-panel';
import type { BillingPlan } from '@/lib/api';

const plans: BillingPlan[] = [
  { plan_version_id: 'p1', plan_code: 'starter', version: 1,
    display_name: 'Inicio', audience_code: 'small_business', catalog_state: 'evaluation',
    features: { multi_company_portfolio: false, team_review_workflows: false,
      advanced_quality_controls: false, foundational_security: true, basic_data_export: true },
    limits: { companies: null, active_members: null, monthly_documents: null, storage_bytes: null },
    commercial: { configured: false, currency_code: null, unit_amount_minor: null, trial_days: null } },
  { plan_version_id: 'p2', plan_code: 'business', version: 1,
    display_name: 'Negocio', audience_code: 'growing_team', catalog_state: 'evaluation',
    features: { multi_company_portfolio: true, team_review_workflows: true,
      advanced_quality_controls: true, foundational_security: true, basic_data_export: true },
    limits: { companies: null, active_members: null, monthly_documents: null, storage_bytes: null },
    commercial: { configured: false, currency_code: null, unit_amount_minor: null, trial_days: null } },
  { plan_version_id: 'p3', plan_code: 'accountant', version: 1,
    display_name: 'Contador', audience_code: 'accounting_practice', catalog_state: 'evaluation',
    features: { multi_company_portfolio: true, team_review_workflows: true,
      advanced_quality_controls: true, foundational_security: true, basic_data_export: true },
    limits: { companies: null, active_members: null, monthly_documents: null, storage_bytes: null },
    commercial: { configured: false, currency_code: null, unit_amount_minor: null, trial_days: null } },
];

describe('BillingPanel', () => {
  it('diferencia evaluacion de cobro y preserva seguridad en todos los planes', () => {
    render(<BillingPanel
      firm={{ firm_id: 'firm-1', legal_name: 'Firma Sintética', firm_role: 'owner' }}
      plans={[...plans]}
      overview={{
        firm_id: 'firm-1', manager_role: 'owner', payments_state: 'disabled',
        subscription: { subscription_id: 'sub-1', status: 'evaluation', sequence: 1,
          source_code: 'self_service_evaluation', started_at: '2026-08-31T00:00:00Z',
          trial_ends_at: null, plan: plans[2]! },
        billing_account: { configuration_state: 'unconfigured', provider_code: null,
          billing_country: null, tax_profile_state: 'unconfigured' },
        usage: { period_start: '2026-08-01', documents_uploaded: 4,
          storage_bytes: 2048, meter_state: 'observed_append_only' },
        history: [],
      }} />);

    expect(screen.getByText('Pagos desactivados')).toBeInTheDocument();
    expect(screen.getByText(/Precios, impuestos y límites finales/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Evaluación activa' })).toBeDisabled();
    expect(screen.getByText(/nunca concede acceso/)).toBeInTheDocument();
    expect(screen.getByText('Para contadores que administran múltiples clientes.')).toBeInTheDocument();
  });
});

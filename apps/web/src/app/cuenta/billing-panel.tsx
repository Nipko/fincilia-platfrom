'use client';

import { useActionState } from 'react';

import {
  selectEvaluationPlanAction,
  type BillingActionState,
} from '@/app/actions';
import type { BillingOverview, BillingPlan, ManagedFirm } from '@/lib/api';

const INITIAL: BillingActionState = { error: null, done: null };

const AUDIENCE: Record<BillingPlan['audience_code'], string> = {
  small_business: 'Para una pequeña empresa que empieza a conciliar.',
  growing_team: 'Para equipos con revisión y varias empresas.',
  accounting_practice: 'Para contadores que administran múltiples clientes.',
};

function featureList(plan: BillingPlan): string[] {
  const features = ['Seguridad, privacidad y exportación básica'];
  if (plan.features.multi_company_portfolio) features.push('Portafolio multiempresa');
  if (plan.features.team_review_workflows) features.push('Flujos de preparación y revisión');
  if (plan.features.advanced_quality_controls) features.push('Controles avanzados de calidad');
  return features;
}

export function BillingPanel({
  firm,
  plans,
  overview,
}: {
  firm: ManagedFirm;
  plans: BillingPlan[];
  overview: BillingOverview;
}) {
  const [state, action, pending] = useActionState(
    selectEvaluationPlanAction, INITIAL,
  );
  const current = overview.subscription?.plan.plan_code ?? null;
  return (
    <article className="billing-workspace">
      <header className="candidate-heading">
        <div>
          <p className="eyebrow">{firm.legal_name}</p>
          <h3>Plan y uso</h3>
          <p className="meta">
            Evaluación funcional sin cobro. Precios, impuestos y límites finales
            todavía no están publicados.
          </p>
        </div>
        <span className="tag">Pagos desactivados</span>
      </header>
      <div className="billing-usage" aria-label="Uso observado este mes">
        <div><strong>{overview.usage.documents_uploaded}</strong><span>documentos</span></div>
        <div><strong>{overview.usage.storage_bytes.toLocaleString('es-CO')}</strong><span>bytes</span></div>
        <div><strong>{overview.subscription?.plan.display_name ?? 'Sin plan'}</strong><span>estado actual</span></div>
      </div>
      <div className="billing-plans">
        {plans.map((plan) => {
          const selected = current === plan.plan_code;
          return (
            <section className={`card billing-plan ${selected ? 'billing-plan--current' : ''}`}
              key={plan.plan_version_id} aria-label={`Plan ${plan.display_name}`}>
              <div>
                <p className="eyebrow">{selected ? 'Plan actual' : 'Disponible'}</p>
                <h4>{plan.display_name}</h4>
                <p>{AUDIENCE[plan.audience_code]}</p>
              </div>
              <ul>{featureList(plan).map((item) => <li key={item}>{item}</li>)}</ul>
              <p className="meta">Precio y capacidad: pendiente de configuración comercial.</p>
              <form action={action}>
                <input type="hidden" name="firmId" value={firm.firm_id} />
                <input type="hidden" name="planCode" value={plan.plan_code} />
                <button type="submit" className={selected ? 'secondary' : undefined}
                  disabled={pending || selected}>
                  {selected ? 'Evaluación activa' : pending ? 'Aplicando…' : 'Usar en evaluación'}
                </button>
              </form>
            </section>
          );
        })}
      </div>
      {state.error ? <p className="error" role="alert">{state.error}</p> : null}
      {state.done ? <p className="notice" role="status">{state.done}</p> : null}
      <p className="meta">
        Un plan solo limita capacidad: nunca concede acceso a empresas, roles o datos.
      </p>
    </article>
  );
}

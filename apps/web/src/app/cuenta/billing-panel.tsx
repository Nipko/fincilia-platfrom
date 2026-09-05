'use client';

import { useActionState } from 'react';

import {
  openStripePortalAction,
  selectEvaluationPlanAction,
  startStripeCheckoutAction,
  type BillingActionState,
} from '@/app/actions';
import type { BillingOverview, BillingPlan, ManagedFirm } from '@/lib/api';
import { CapabilityStatus } from '@/components/capability-status';
import {
  formatBytes,
  formatLimit,
  formatMinorAmount,
  formatWebMoment,
  usagePercent,
} from '@/lib/web-capabilities';

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

const SUBSCRIPTION_LABELS: Record<NonNullable<BillingOverview['subscription']>['status'], string> = {
  evaluation: 'Evaluación',
  trialing: 'Periodo de prueba',
  active: 'Activa',
  past_due: 'Pago pendiente',
  superseded: 'Sustituida',
  canceled: 'Cancelada',
};

function UsageMeter({
  label,
  value,
  limit,
  formattedValue,
  unit,
}: {
  label: string;
  value: number;
  limit: number | null;
  formattedValue: string;
  unit: string;
}) {
  const percent = usagePercent(value, limit);
  return (
    <div className="billing-meter">
      <div><span>{label}</span><strong>{formattedValue}</strong></div>
      {percent === null ? (
        <p className="meta">{formatLimit(limit, unit)}</p>
      ) : <>
        <div aria-label={`${label}: ${percent}% del límite`} aria-valuemax={100}
          aria-valuemin={0} aria-valuenow={percent} className="billing-meter__track"
          role="progressbar">
          <span style={{ width: `${percent}%` }} />
        </div>
        <p className="meta">{percent}% de {formatLimit(limit, unit)}</p>
      </>}
    </div>
  );
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
  const [checkoutState, checkoutAction, checkoutPending] = useActionState(
    startStripeCheckoutAction, INITIAL,
  );
  const [portalState, portalAction, portalPending] = useActionState(
    openStripePortalAction, INITIAL,
  );
  const current = overview.subscription?.plan.plan_code ?? null;
  const currentPlan = overview.subscription?.plan ?? null;
  const paymentReady = overview.payments_state === 'ready';
  const hasStripeCustomer = overview.billing_account.provider_code === 'stripe';
  return (
    <article className="billing-workspace">
      <header className="candidate-heading">
        <div>
          <p className="eyebrow">{firm.legal_name}</p>
          <h3>Plan y uso</h3>
          <p className="meta">
            {paymentReady
              ? 'Checkout y gestión de la suscripción se realizan en páginas seguras alojadas por Stripe.'
              : 'Evaluación funcional sin cobro. Los precios y límites comerciales se publicarán al cerrar los planes.'}
          </p>
        </div>
        <div className="billing-heading-actions">
          <span className={`tag ${paymentReady ? 'tag--success' : ''}`}>
            {paymentReady ? 'Stripe habilitado' : 'Pagos desactivados'}
          </span>
          {paymentReady && hasStripeCustomer ? (
            <form action={portalAction}>
              <input type="hidden" name="firmId" value={firm.firm_id} />
              <button className="secondary" type="submit" disabled={portalPending}>
                {portalPending ? 'Abriendo…' : 'Gestionar facturación'}
              </button>
            </form>
          ) : null}
        </div>
      </header>
      <div className="billing-usage" aria-label="Uso observado este mes">
        <UsageMeter label="Documentos" value={overview.usage.documents_uploaded}
          limit={currentPlan?.limits.monthly_documents ?? null}
          formattedValue={overview.usage.documents_uploaded.toLocaleString('es-CO')}
          unit="documentos" />
        <UsageMeter label="Almacenamiento" value={overview.usage.storage_bytes}
          limit={currentPlan?.limits.storage_bytes ?? null}
          formattedValue={formatBytes(overview.usage.storage_bytes)} unit="bytes" />
        <div className="billing-current">
          <span>Estado actual</span>
          <strong>{overview.subscription?.plan.display_name ?? 'Sin plan'}</strong>
          <p className="meta">
            {overview.subscription
              ? `${SUBSCRIPTION_LABELS[overview.subscription.status]} · desde ${formatWebMoment(overview.subscription.started_at)}`
              : 'Selecciona una capacidad para la evaluación.'}
          </p>
        </div>
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
              <dl className="billing-plan__limits">
                <div><dt>Empresas</dt><dd>{formatLimit(plan.limits.companies, 'empresa(s)')}</dd></div>
                <div><dt>Equipo</dt><dd>{formatLimit(plan.limits.active_members, 'persona(s)')}</dd></div>
                <div><dt>Documentos/mes</dt><dd>{formatLimit(plan.limits.monthly_documents, 'documentos')}</dd></div>
                <div><dt>Almacenamiento</dt><dd>{plan.limits.storage_bytes === null
                  ? 'Sin límite publicado' : formatBytes(plan.limits.storage_bytes)}</dd></div>
              </dl>
              <p className="billing-plan__commercial">
                {plan.commercial.configured && plan.commercial.currency_code
                  && plan.commercial.unit_amount_minor !== null
                  ? `${formatMinorAmount(plan.commercial.unit_amount_minor, plan.commercial.currency_code)} · configuración versionada`
                  : 'Precio, impuestos y capacidad comercial aún no publicados.'}
              </p>
              {paymentReady ? (
                <form action={checkoutAction}>
                  <input type="hidden" name="firmId" value={firm.firm_id} />
                  <input type="hidden" name="planCode" value={plan.plan_code} />
                  <button type="submit" className={selected ? 'secondary' : undefined}
                    disabled={checkoutPending || !plan.commercial.configured}>
                    {!plan.commercial.configured
                      ? 'Precio por publicar'
                      : checkoutPending ? 'Abriendo Stripe…'
                        : selected && hasStripeCustomer ? 'Cambiar plan' : 'Suscribirme'}
                  </button>
                </form>
              ) : (
                <form action={action}>
                  <input type="hidden" name="firmId" value={firm.firm_id} />
                  <input type="hidden" name="planCode" value={plan.plan_code} />
                  <button type="submit" className={selected ? 'secondary' : undefined}
                    disabled={pending || selected}>
                    {selected ? 'Evaluación activa' : pending ? 'Aplicando…' : 'Usar en evaluación'}
                  </button>
                </form>
              )}
            </section>
          );
        })}
      </div>
      {state.error ? <p className="error" role="alert">{state.error}</p> : null}
      {state.done ? <p className="notice" role="status">{state.done}</p> : null}
      {checkoutState.error ? <p className="error" role="alert">{checkoutState.error}</p> : null}
      {portalState.error ? <p className="error" role="alert">{portalState.error}</p> : null}
      <section aria-labelledby={`billing-readiness-${firm.firm_id}`}>
        <div className="section-heading">
          <div><p className="eyebrow">Preparación comercial</p>
            <h4 id={`billing-readiness-${firm.firm_id}`}>Qué está activo y qué no</h4></div>
        </div>
        <div className="capability-grid">
          <CapabilityStatus state={paymentReady ? 'available' : 'blocked'}
            title="Proveedor de pagos"
            description={paymentReady
              ? 'Stripe está configurado; Fincilia no almacena números de tarjeta ni códigos de seguridad.'
              : 'Stripe está seleccionado, pero no recibe credenciales mientras los pagos estén apagados.'} />
          <CapabilityStatus
            state={overview.billing_account.tax_profile_state === 'verified' ? 'available' : 'blocked'}
            title="Perfil tributario"
            description={`Estado: ${overview.billing_account.tax_profile_state}. No se calculan impuestos sin verificación.`} />
          <CapabilityStatus state={paymentReady ? 'available' : 'blocked'}
            title="Checkout y cobros"
            description={paymentReady
              ? 'Checkout alojado y webhook firmado; el retorno del navegador nunca activa el plan.'
              : 'Deshabilitados por contrato. Elegir un plan de evaluación no genera cargos.'} />
        </div>
      </section>
      <section aria-labelledby={`billing-history-${firm.firm_id}`}>
        <h4 id={`billing-history-${firm.firm_id}`}>Historial de capacidad</h4>
        {overview.history.length ? (
          <ol className="billing-history">
            {overview.history.map((event, index) => (
              <li key={`${event.occurred_at}:${event.event_code}:${index}`}>
                <div><strong>{event.plan_code}</strong><span>{event.event_code}</span></div>
                <small>{formatWebMoment(event.occurred_at)} · {event.reason_code}</small>
              </li>
            ))}
          </ol>
        ) : <p className="meta">Aún no hay cambios de capacidad registrados.</p>}
      </section>
      <p className="meta">
        Un plan solo limita capacidad: nunca concede acceso a empresas, roles o datos.
      </p>
    </article>
  );
}

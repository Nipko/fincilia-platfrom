'use client';

import Link from 'next/link';
import { useActionState } from 'react';

import {
  syncNotificationRemindersAction,
  updateNotificationPreferenceAction,
  type NotificationActionState,
} from '@/app/actions';
import type { NotificationDelivery, NotificationPreference } from '@/lib/api';
import { CapabilityStatus } from '@/components/capability-status';
import {
  DELIVERY_LABELS,
  SUPPRESSION_LABELS,
  formatWebMoment,
  summarizeDeliveries,
} from '@/lib/web-capabilities';

const INITIAL: NotificationActionState = { error: null, done: null };

export function NotificationControls({
  companyId,
  preference,
  deliveries,
}: {
  companyId: string;
  preference: NotificationPreference;
  deliveries: NotificationDelivery[];
}) {
  const [preferenceState, save, saving] = useActionState(
    updateNotificationPreferenceAction, INITIAL,
  );
  const [syncState, sync, syncing] = useActionState(
    syncNotificationRemindersAction, INITIAL,
  );
  const summary = summarizeDeliveries(deliveries);
  return (
    <section className="card notification-center" aria-labelledby="notification-title">
      <div className="candidate-heading">
        <div>
          <h2 id="notification-title">Avisos por correo</h2>
          <p className="meta">
            Preferencia por empresa. El proveedor externo aun no esta configurado:
            cualquier intento queda suprimido y nunca aparece como enviado.
          </p>
        </div>
        <span className="tag">Entrega externa desactivada</span>
      </div>
      <CapabilityStatus state="blocked" title="Canal de correo"
        description="Las preferencias y las intenciones quedan registradas, pero ningún mensaje se presenta como enviado mientras el proveedor esté apagado."
        detail={<span>Destino: {preference.destination_state === 'provider_configuration_pending'
          ? 'configuración del proveedor pendiente' : preference.destination_state}</span>} />
      <form action={save} className="notification-preferences">
        <input type="hidden" name="companyId" value={companyId} />
        <label className="check-row">
          <input name="enabled" type="checkbox" value="yes"
            defaultChecked={preference.enabled} />
          Preparar avisos operativos por correo
        </label>
        <label>Idioma<select name="locale" defaultValue={preference.locale}>
          <option value="es-CO">Español (Colombia)</option>
          <option value="en-US">English (US)</option>
        </select></label>
        <label>Zona horaria<input name="timezone" required
          defaultValue={preference.timezone} /></label>
        <label>Silencio desde<input name="quietFrom" type="time" required
          defaultValue={preference.quiet_from} /></label>
        <label>Silencio hasta<input name="quietUntil" type="time" required
          defaultValue={preference.quiet_until} /></label>
        <button type="submit" disabled={saving}>
          {saving ? 'Guardando…' : 'Guardar preferencia'}
        </button>
        {preferenceState.error ? <p className="error" role="alert">{preferenceState.error}</p> : null}
        {preferenceState.done ? <p className="notice" role="status">{preferenceState.done}</p> : null}
      </form>
      <form action={sync}>
        <input type="hidden" name="companyId" value={companyId} />
        <button type="submit" className="secondary" disabled={syncing}>
          {syncing ? 'Sincronizando…' : 'Preparar avisos pendientes'}
        </button>
        {syncState.error ? <p className="error" role="alert">{syncState.error}</p> : null}
        {syncState.done ? <p className="notice" role="status">{syncState.done}</p> : null}
      </form>
      <dl className="notification-summary" aria-label="Resumen de entregas visibles">
        <div><dt>En cola</dt><dd>{summary.queued}</dd></div>
        <div><dt>Entregadas</dt><dd>{summary.delivered}</dd></div>
        <div><dt>Fallidas</dt><dd>{summary.failed}</dd></div>
        <div><dt>Suprimidas</dt><dd>{summary.suppressed}</dd></div>
      </dl>
      <div>
        <h3>Historial verificable</h3>
        <p className="meta">Últimas {deliveries.length} intenciones visibles para tu cuenta.</p>
      </div>
      {deliveries.length ? (
        <ol className="notification-history">
          {deliveries.map((delivery) => (
            <li key={delivery.delivery_id}>
              <div className="notification-history__heading">
                <strong>{delivery.context.period_label}</strong>
                <span className={`status-pill notification-status--${delivery.status}`}>
                  {DELIVERY_LABELS[delivery.status]}
                </span>
              </div>
              <span className="meta">Vence {delivery.context.due_on} · creada {formatWebMoment(delivery.created_at)}</span>
              {delivery.suppression_reason ? (
                <span className="notification-reason">
                  {SUPPRESSION_LABELS[delivery.suppression_reason] ?? delivery.suppression_reason}
                </span>
              ) : null}
              <div className="notification-history__footer">
                <small>{delivery.attempt_count} intento(s)</small>
                <Link href={delivery.context.action_url}>Abrir ciclo</Link>
              </div>
            </li>
          ))}
        </ol>
      ) : <p className="meta">Todavia no hay intenciones de entrega.</p>}
    </section>
  );
}

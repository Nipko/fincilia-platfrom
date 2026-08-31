'use client';

import { useActionState } from 'react';

import {
  syncNotificationRemindersAction,
  updateNotificationPreferenceAction,
  type NotificationActionState,
} from '@/app/actions';
import type { NotificationDelivery, NotificationPreference } from '@/lib/api';

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
        <span className="tag">Adaptador desactivado</span>
      </div>
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
      <h3>Historial verificable</h3>
      {deliveries.length ? (
        <ol className="notification-history">
          {deliveries.map((delivery) => (
            <li key={delivery.delivery_id}>
              <strong>{delivery.context.period_label}</strong> · {delivery.status}
              {delivery.suppression_reason ? ` · ${delivery.suppression_reason}` : ''}
              <span className="meta">Vence {delivery.context.due_on}</span>
            </li>
          ))}
        </ol>
      ) : <p className="meta">Todavia no hay intenciones de entrega.</p>}
    </section>
  );
}

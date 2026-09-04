import type { ReactNode } from 'react';

export type CapabilityState = 'available' | 'conditional' | 'blocked' | 'planned';

const STATE_LABELS: Readonly<Record<CapabilityState, string>> = {
  available: 'Disponible',
  conditional: 'Disponible con condiciones',
  blocked: 'No habilitado',
  planned: 'Preparado para configurar',
};

export function CapabilityStatus({
  state,
  title,
  description,
  detail,
}: Readonly<{
  state: CapabilityState;
  title: string;
  description: string;
  detail?: ReactNode;
}>) {
  return (
    <article className={`capability-status capability-status--${state}`}>
      <div className="capability-status__heading">
        <h3>{title}</h3>
        <span className="status-pill" data-state={state}>{STATE_LABELS[state]}</span>
      </div>
      <p>{description}</p>
      {detail === undefined ? null : (
        <div className="capability-status__detail">{detail}</div>
      )}
    </article>
  );
}

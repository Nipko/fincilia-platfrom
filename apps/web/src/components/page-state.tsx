import type { ReactNode } from 'react';

export type PageStateKind =
  | 'empty'
  | 'denied'
  | 'degraded'
  | 'loading'
  | 'not-found';

type PageStateProps = Readonly<{
  kind: PageStateKind;
  title: string;
  description: string;
  action?: ReactNode;
  headingAs?: 'h1' | 'h2';
}>;

const LABELS: Readonly<Record<PageStateKind, string>> = {
  empty: 'Sin resultados',
  denied: 'Acceso denegado',
  degraded: 'Servicio no disponible',
  loading: 'Cargando',
  'not-found': 'No encontrado',
};

export function PageState({
  kind,
  title,
  description,
  action,
  headingAs: Heading = 'h2',
}: PageStateProps) {
  const isAlert = kind === 'denied' || kind === 'degraded';
  const isLoading = kind === 'loading';

  return (
    <section
      aria-atomic="true"
      aria-busy={isLoading}
      aria-label={title}
      aria-live={isAlert ? 'assertive' : 'polite'}
      className={`page-state page-state--${kind}`}
      role={isAlert ? 'alert' : 'status'}
    >
      <p className="page-state__label">{LABELS[kind]}</p>
      <Heading>{title}</Heading>
      <p className="page-state__description">{description}</p>
      {action === undefined ? null : (
        <div className="page-state__action">{action}</div>
      )}
    </section>
  );
}

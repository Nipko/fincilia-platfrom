'use client';

import Link from 'next/link';
import { useActionState } from 'react';

import { applyTemplateMappingAction, type TemplateMappingState } from '@/app/actions';
import type { TemplateOffer } from '@/lib/simple-mode';

const INITIAL: TemplateMappingState = { error: null };

/**
 * Despues de procesar el documento: un boton si la plantilla encaja de forma
 * inequivoca; si no, el mapeo manual de siempre. La plantilla bancaria es una
 * hipotesis sintetica y se dice en la etiqueta.
 */
export function TemplateOfferPanel({
  companyId, artifactId, dataSourceId, offer, manualHref,
}: {
  companyId: string;
  artifactId: string;
  dataSourceId: string | null;
  offer: TemplateOffer;
  manualHref: string;
}) {
  const [state, action, pending] = useActionState(applyTemplateMappingAction, INITIAL);
  if (offer.kind === 'pending') return null;
  return (
    <section className="card template-offer" aria-labelledby="template-offer-heading">
      <h2 id="template-offer-heading">Columnas del archivo</h2>
      {offer.kind === 'template' && dataSourceId ? (
        <form action={action}>
          <input type="hidden" name="companyId" value={companyId} />
          <input type="hidden" name="artifactId" value={artifactId} />
          <input type="hidden" name="dataSourceId" value={dataSourceId} />
          {offer.warning ? (
            <p className="notice" id="template-offer-warning">{offer.warning}</p>
          ) : (
            <p className="meta">
              Este formato tiene una estructura fija; se lee sin elegir columnas.
            </p>
          )}
          <button type="submit" disabled={pending}
            aria-describedby={offer.warning ? 'template-offer-warning' : undefined}>
            {pending ? 'Aplicando...' : offer.label}
          </button>{' '}
          <Link href={manualHref}>Prefiero mapear a mano</Link>
          {state.error ? <p className="notice error" role="alert">{state.error}</p> : null}
        </form>
      ) : (
        <p>
          No reconocimos el formato de forma inequívoca.{' '}
          <Link href={manualHref}>Asignar las columnas a mano →</Link>
        </p>
      )}
    </section>
  );
}

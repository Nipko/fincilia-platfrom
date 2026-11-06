import Link from 'next/link';
import type { ReactNode } from 'react';

import { ReviewModeBadge } from '@/components/review-mode-badge';
import type { AccountingPeriodClose } from '@/lib/api';
import {
  closeCertificationView,
  mayOfferCertification,
  type PendingEntry,
} from '@/lib/simple-mode';
import { CertifyCloseControl } from './certify-control';
import { SimpleInbox, type SimpleInboxProps } from './simple-inbox';
import { PeriodSummaryCard, UploadScheduleCard } from './simple-summary';
import type { ReconciliationSummary, UploadSchedule } from '@/lib/api';

const KIND_LABELS: Record<PendingEntry['kind'], string> = {
  candidate: 'Cruce',
  dataset: 'Archivo',
  item: 'Partida',
  difference: 'Saldo',
};

/** Resultado de una consulta: `null` significa que no se pudo saber. */
export type SimpleHomeProps = {
  companyId: string;
  actorId: string;
  permissions: readonly string[];
  upload: ReactNode;
  pending: PendingEntry[] | null;
  pendingPartial: boolean;
  close: AccountingPeriodClose | null | 'restricted' | 'unavailable';
  inbox?: SimpleInboxProps | null;
  summary?: ReconciliationSummary | 'restricted' | 'unavailable';
  schedule?: UploadSchedule | 'restricted' | 'unavailable';
};

function PendingInbox({ pending, partial, hasInboxItems }: {
  pending: PendingEntry[] | null;
  partial: boolean;
  hasInboxItems: boolean;
}) {
  if (pending === null) {
    return (
      <p className="notice" role="status">
        Tu acceso no permite consultar los pendientes de esta empresa.
      </p>
    );
  }
  return (
    <>
      {partial ? (
        <p className="notice" role="status">
          Parte de la información no se pudo consultar; puede haber más pendientes.
        </p>
      ) : null}
      {pending.length === 0 ? (
        hasInboxItems ? null : (
          <p className="card" role="status">
            No hay nada pendiente por revisar ahora mismo.
          </p>
        )
      ) : (
        <ul className="pending-list" aria-label="Pendientes por revisar">
          {pending.map((entry) => (
            <li className="card pending-item" key={entry.key}>
              <div className="tags">
                <span className="tag tag--muted">{KIND_LABELS[entry.kind]}</span>
                <ReviewModeBadge mode={entry.reviewMode} />
              </div>
              <h4>{entry.title}</h4>
              <p className="meta">{entry.detail}</p>
              {entry.explanation.length ? (
                <ul aria-label="Por qué aparece">
                  {entry.explanation.map((line, index) => (
                    <li key={`${entry.key}:${index}`}>{line}</li>
                  ))}
                </ul>
              ) : null}
              <Link href={entry.href}>Revisar →</Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function CloseStatus({
  companyId, actorId, permissions, close,
}: Pick<SimpleHomeProps, 'companyId' | 'actorId' | 'permissions' | 'close'>) {
  if (close === 'restricted') {
    return <p className="meta">Tu acceso no permite ver el estado del cierre.</p>;
  }
  if (close === 'unavailable') {
    return (
      <p className="notice" role="status">
        No se pudo consultar el estado del cierre en este momento.
      </p>
    );
  }
  if (close === null) {
    return (
      <p>
        Aún no has cerrado ningún periodo. Cuando no queden pendientes, prepara
        el cierre del mes.
      </p>
    );
  }
  const view = closeCertificationView(close);
  return (
    <div className={`card close-certification close-certification--${view.state}`}>
      <p className="eyebrow">Periodo {close.period_start} a {close.period_end}</p>
      <p><strong>{view.label}</strong></p>
      <p className="meta">Cerrado por {close.closer_name}.</p>
      {view.state === 'self_reviewed' ? (
        <p className="meta">
          Tu contador u otra persona con acceso de revisión puede certificarlo
          después. Mientras tanto puedes seguir operando.
        </p>
      ) : null}
      {mayOfferCertification(close, actorId, permissions) ? (
        <CertifyCloseControl companyId={companyId} closeId={close.close_id} />
      ) : null}
    </div>
  );
}

export function SimpleHome(props: SimpleHomeProps) {
  const { companyId } = props;
  const encoded = encodeURIComponent(companyId);
  return (
    <section className="workspace-section" aria-labelledby="simple-steps-heading">
      <div className="section-heading mode-switch">
        <div>
          <p className="eyebrow">Modo simple</p>
          <h2 id="simple-steps-heading">Tu mes en tres pasos</h2>
        </div>
        <Link href={`/empresas/${encoded}/flujo-contable`}>Modo contador →</Link>
      </div>

      <ol className="simple-steps" aria-label="Pasos del modo simple">
        <li className="card simple-step">
          <header>
            <span className="simple-step__number" aria-hidden="true">1</span>
            <h3 id="simple-step-upload">Subir</h3>
          </header>
          <p>
            Sube el extracto del banco y tus facturas electrónicas o la
            exportación de tu sistema de facturación.
          </p>
          {props.upload}
          {props.schedule ? (
            <UploadScheduleCard companyId={companyId} schedule={props.schedule} />
          ) : null}
        </li>

        <li className="card simple-step">
          <header>
            <span className="simple-step__number" aria-hidden="true">2</span>
            <h3 id="simple-step-review">Revisar pendientes</h3>
          </header>
          <p>Solo aparece lo que no cuadra o espera tu decisión.</p>
          {props.summary ? <PeriodSummaryCard summary={props.summary} /> : null}
          {props.inbox ? <SimpleInbox {...props.inbox} /> : null}
          <PendingInbox
            pending={props.inbox
              ? props.pending?.filter((entry) => entry.kind !== 'candidate') ?? null
              : props.pending}
            partial={props.pendingPartial}
            hasInboxItems={Boolean(props.inbox && (props.inbox.decisions.length
              || props.inbox.unpaired.length || props.inbox.applications.length))} />
          <Link href={`/empresas/${encoded}/reglas`}>Reglas de conciliación →</Link>
        </li>

        <li className="card simple-step">
          <header>
            <span className="simple-step__number" aria-hidden="true">3</span>
            <h3 id="simple-step-done">Listo</h3>
          </header>
          <CloseStatus companyId={companyId} actorId={props.actorId}
            permissions={props.permissions} close={props.close} />
          {props.permissions.includes('report.read') ? (
            <Link href={`/preparacion-cierre?empresa=${encoded}`}>Preparar o revisar el cierre →</Link>
          ) : null}
        </li>
      </ol>
    </section>
  );
}

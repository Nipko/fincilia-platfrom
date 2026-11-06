'use client';

import { useActionState } from 'react';

import { changeUploadScheduleAction, type UploadScheduleState } from '@/app/actions';
import type { ReconciliationSummary, UploadSchedule } from '@/lib/api';
import {
  CADENCE_OPTIONS,
  cadenceLabel,
  summaryLine,
  uploadReminderText,
} from '@/lib/simple-mode';

const INITIAL: UploadScheduleState = { error: null, done: null };

/** Tarjeta del periodo: conteos, nunca importes ni una conclusion de cuadre. */
export function PeriodSummaryCard({ summary }: {
  summary: ReconciliationSummary | 'restricted' | 'unavailable';
}) {
  if (summary === 'restricted') return null;
  if (summary === 'unavailable') {
    return (
      <p className="notice" role="status">
        No se pudo calcular el resumen del periodo en este momento.
      </p>
    );
  }
  return (
    <section className="card period-summary" aria-labelledby="period-summary-heading">
      <p className="eyebrow">Este mes · {summary.period_start} a {summary.period_end}</p>
      <h3 id="period-summary-heading">{summaryLine(summary)}</h3>
      <p className="meta">
        Cuenta movimientos de archivos verificados. Un cruce deshecho vuelve a
        pendientes. No es un saldo ni prueba que el mes cuadre.
      </p>
    </section>
  );
}

export function UploadScheduleCard({ companyId, schedule }: {
  companyId: string;
  schedule: UploadSchedule | 'restricted' | 'unavailable';
}) {
  const [state, action, pending] = useActionState(changeUploadScheduleAction, INITIAL);
  if (schedule === 'restricted') return null;
  if (schedule === 'unavailable') {
    return (
      <p className="notice" role="status">
        No se pudo consultar la frecuencia de carga.
      </p>
    );
  }
  return (
    <section className="card upload-schedule" aria-labelledby="upload-schedule-heading">
      <h3 id="upload-schedule-heading">¿Cada cuánto subes tu extracto?</h3>
      <p role="status">{uploadReminderText(schedule)}</p>
      {schedule.can_change ? (
        <form action={action} className="inline-form">
          <input type="hidden" name="companyId" value={companyId} />
          <fieldset>
            <legend className="meta">Frecuencia</legend>
            {CADENCE_OPTIONS.map((option) => (
              <label key={option.cadence} className="radio-option">
                <input type="radio" name="cadence" value={option.cadence}
                  defaultChecked={schedule.cadence === option.cadence} required />
                {option.label}
              </label>
            ))}
          </fieldset>
          <button type="submit" className="secondary" disabled={pending}>
            {pending ? 'Guardando...' : 'Guardar frecuencia'}
          </button>
        </form>
      ) : (
        <p className="meta">
          Frecuencia: {cadenceLabel(schedule.cadence)}. Solo el dueño de la
          empresa puede cambiarla.
        </p>
      )}
      {state.error ? <p className="notice error" role="alert">{state.error}</p> : null}
      {state.done ? <p className="notice ok" role="status">{state.done}</p> : null}
      <p className="meta">
        Los recordatorios aparecen dentro de Fincilia. No enviamos correos ni
        mensajes de WhatsApp.
      </p>
    </section>
  );
}

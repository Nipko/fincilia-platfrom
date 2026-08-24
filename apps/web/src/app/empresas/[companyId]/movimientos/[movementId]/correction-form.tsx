'use client';

import { useActionState, useState } from 'react';

import { proposeCorrectionAction } from '@/app/actions';
import type { CorrectionTarget } from '@/lib/api';
import { CORRECTION_FIELD_LABELS, correctionInput } from '@/lib/corrections';

const INITIAL = { error: null, done: null };

export function CorrectionProposalForm({
  companyId,
  artifactId,
  datasetVersionId,
  movementId,
  targets,
}: {
  companyId: string;
  artifactId: string;
  datasetVersionId: string;
  movementId: string;
  targets: CorrectionTarget[];
}) {
  const [selectedField, setSelectedField] = useState(targets[0]?.field ?? '');
  const [state, action, pending] = useActionState(proposeCorrectionAction, INITIAL);
  const selected = targets.find((item) => item.field === selectedField) ?? targets[0];
  if (!selected) {
    return <p className="notice">No hay campos corregibles en esta version.</p>;
  }
  const input = correctionInput(selected);

  return (
    <form className="upload correction-form" action={action}>
      <input type="hidden" name="companyId" value={companyId} />
      <input type="hidden" name="artifactId" value={artifactId} />
      <input type="hidden" name="datasetVersionId" value={datasetVersionId} />
      <input type="hidden" name="movementId" value={movementId} />
      <input
        type="hidden"
        name="expectedBaseDigest"
        value={selected.expected_base_digest}
      />

      <label htmlFor="correction-field">Campo a corregir</label>
      <select
        id="correction-field"
        name="field"
        value={selected.field}
        onChange={(event) => setSelectedField(event.target.value)}
      >
        {targets.map((target) => (
          <option key={target.field} value={target.field}>
            {CORRECTION_FIELD_LABELS[target.field] ?? target.field}
          </option>
        ))}
      </select>

      <p className="meta">
        Valor actual: <strong>{selected.current_value ?? 'sin valor'}</strong>. La
        propuesta no lo sobrescribe.
      </p>
      <label htmlFor="correction-new-value">Nuevo valor tipado</label>
      <input
        key={selected.field}
        id="correction-new-value"
        name="newValue"
        required
        type={input.type}
        inputMode={input.inputMode}
        pattern={input.pattern}
        placeholder={input.placeholder}
        maxLength={128}
        autoComplete="off"
      />

      <label htmlFor="correction-reason-code">Clase de motivo</label>
      <select id="correction-reason-code" name="reasonCode" required>
        <option value="source_correction">Correccion contra la fuente</option>
        <option value="bank_clarification">Aclaracion de la entidad</option>
        <option value="accounting_adjustment">Criterio contable</option>
        <option value="date_correction">Correccion de fecha</option>
        <option value="classification_correction">Correccion de clasificacion</option>
        <option value="other_reviewed">Otro motivo revisable</option>
      </select>
      <label htmlFor="correction-comment">Explicacion para el revisor</label>
      <textarea
        id="correction-comment"
        name="reasonComment"
        required
        maxLength={500}
        aria-describedby="correction-warning"
      />
      <p id="correction-warning" className="meta">
        No copies credenciales ni datos personales. Aprobar autorizara un
        reproceso posterior; no cambiara este movimiento.
      </p>
      <button type="submit" disabled={pending}>
        {pending ? 'Proponiendo...' : 'Enviar a revision'}
      </button>
      {state.error ? <p className="notice error" role="alert">{state.error}</p> : null}
      {state.done ? <p className="notice ok" role="status">{state.done}</p> : null}
    </form>
  );
}

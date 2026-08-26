'use client';

import { useActionState, useId, useMemo, useState } from 'react';

import {
  proposeMatchGroupAction,
  type MatchReviewState,
} from '@/app/actions';
import type { Movement } from '@/lib/api';
import { formatExactMoney } from '@/lib/reconciliation';

const INITIAL: MatchReviewState = { error: null, done: null };

function Feedback({ state }: { state: MatchReviewState }) {
  if (state.error) return <p className="notice error" role="alert">{state.error}</p>;
  if (state.done) return <p className="notice ok" role="status">{state.done}</p>;
  return null;
}

function movementLabel(movement: Movement): string {
  const direction = movement.direction === 'outflow' ? 'salida' : 'entrada';
  return (
    `Fila ${movement.record_ordinal} · ` +
    `${formatExactMoney(movement.amount, movement.currency)} · ${direction}`
  );
}

export function GroupProposalForm({
  companyId,
  anchorDatasetId,
  relatedDatasetId,
  anchorSide,
  anchors,
  related,
  commandKey,
}: {
  companyId: string;
  anchorDatasetId: string;
  relatedDatasetId: string;
  anchorSide: 'izquierdo' | 'derecho';
  anchors: Movement[];
  related: Movement[];
  commandKey: string;
}) {
  const [state, action, pending] = useActionState(proposeMatchGroupAction, INITIAL);
  const [anchorId, setAnchorId] = useState(anchors[0]?.movement_id ?? '');
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const descriptionId = useId();
  const anchor = anchors.find((movement) => movement.movement_id === anchorId);
  const eligibleRelated = useMemo(() => (
    anchor
      ? related.filter((movement) => (
          movement.currency === anchor.currency &&
          movement.direction !== anchor.direction
        ))
      : []
  ), [anchor, related]);

  function changeAnchor(next: string) {
    setAnchorId(next);
    setSelected(new Set());
  }

  function toggle(movementId: string, checked: boolean) {
    setSelected((current) => {
      const next = new Set(current);
      if (checked) next.add(movementId);
      else next.delete(movementId);
      return next;
    });
  }

  const relation = anchorSide === 'izquierdo' ? '1:N' : 'N:1';
  return (
    <form className="group-proposal-form" action={action}
      aria-label={`Crear propuesta ${relation}`}>
      <input type="hidden" name="companyId" value={companyId} />
      <input type="hidden" name="anchorDatasetId" value={anchorDatasetId} />
      <input type="hidden" name="relatedDatasetId" value={relatedDatasetId} />
      <input type="hidden" name="idempotencyKey" value={commandKey} />
      <div className="group-proposal-form__heading">
        <div>
          <strong>{relation} · ancla del dataset {anchorSide}</strong>
          <p className="meta" id={descriptionId}>
            Elige un movimiento y al menos dos del dataset opuesto. La API
            vuelve a validar moneda, direccion, cuenta, linaje y completitud.
          </p>
        </div>
        <span className="tag">borrador</span>
      </div>

      <label>
        Movimiento ancla
        <select name="anchorMovementId" value={anchorId}
          onChange={(event) => changeAnchor(event.currentTarget.value)}
          aria-describedby={descriptionId} required>
          {anchors.map((movement) => (
            <option value={movement.movement_id} key={movement.movement_id}>
              {movementLabel(movement)}
            </option>
          ))}
        </select>
      </label>

      <fieldset className="group-member-picker">
        <legend>Movimientos relacionados ({selected.size} seleccionados)</legend>
        {eligibleRelated.length < 2 ? (
          <p className="meta">
            Este ancla no tiene dos movimientos visibles con moneda y direccion compatibles.
          </p>
        ) : (
          eligibleRelated.map((movement) => (
            <label className="group-member-option" key={movement.movement_id}>
              <input type="checkbox" name="relatedMovementIds"
                value={movement.movement_id}
                checked={selected.has(movement.movement_id)}
                disabled={pending || (!selected.has(movement.movement_id) && selected.size >= 49)}
                onChange={(event) => toggle(
                  movement.movement_id, event.currentTarget.checked)} />
              <span>
                <strong>{movementLabel(movement)}</strong>
                <span>{movement.occurred_on} · {movement.description}</span>
              </span>
            </label>
          ))
        )}
      </fieldset>

      <button type="submit" disabled={pending || !anchorId || selected.size < 2}>
        {pending ? 'Registrando borrador...' : `Guardar propuesta ${relation}`}
      </button>
      <Feedback state={state} />
    </form>
  );
}

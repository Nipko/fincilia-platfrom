'use client';

import { useActionState } from 'react';

import type { SpreadsheetWorkspace } from '@/lib/api';
import {
  selectSpreadsheetSheetAction,
  type SpreadsheetSelectionState,
} from '../../../../actions';

const INITIAL: SpreadsheetSelectionState = { error: null, selected: null };

export function SheetSelector({
  companyId,
  artifactId,
  workspace,
}: {
  companyId: string;
  artifactId: string;
  workspace: SpreadsheetWorkspace;
}) {
  const [state, action, pending] = useActionState(
    selectSpreadsheetSheetAction, INITIAL);
  const visible = workspace.sheets.filter((sheet) => sheet.state === 'visible');

  return (
    <form action={action} className="sheet-selector">
      <input type="hidden" name="companyId" value={companyId} />
      <input type="hidden" name="artifactId" value={artifactId} />
      <fieldset>
        <legend>Elige la hoja que contiene los movimientos</legend>
        <p className="meta">
          Se inspeccionaron {workspace.sheet_count} hojas sin ejecutar formulas.
          Esta eleccion queda ligada a la huella del libro y no modifica el original.
        </p>
        <div className="sheet-grid">
          {visible.map((sheet) => (
            <label className="sheet-option" key={sheet.sheet_identity}>
              <input
                type="radio"
                name="sheetIdentity"
                value={sheet.sheet_identity}
                required
              />
              <span>
                <strong>{sheet.name}</strong>
                <small>Hoja {sheet.ordinal} · visible</small>
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      <button type="submit" disabled={pending || visible.length === 0}>
        {pending ? 'Preparando hoja...' : 'Usar esta hoja'}
      </button>
      {state.error ? <p className="notice error" role="alert">{state.error}</p> : null}
      {state.selected ? (
        <p className="notice ok" role="status">
          Hoja {state.selected} seleccionada. Perfil y extraccion quedaron en cola.
        </p>
      ) : null}
    </form>
  );
}

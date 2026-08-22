'use client';

import { useActionState } from 'react';

import { uploadDocumentAction, type UploadState } from '../../actions';

const INITIAL: UploadState = { error: null, uploaded: null };

export function UploadForm({ companyId }: { companyId: string }) {
  const [state, action, pending] = useActionState(uploadDocumentAction, INITIAL);

  return (
    <form className="upload" action={action}>
      <input type="hidden" name="companyId" value={companyId} />
      <label>
        Subir un extracto o soporte
        <input name="file" type="file" accept=".csv,.pdf,.xlsx,.ods,.zip" required />
      </label>
      <div>
        <button type="submit" disabled={pending}>
          {pending ? 'Subiendo...' : 'Subir'}
        </button>
      </div>
      {state.error ? (
        <p className="notice error" role="alert">
          {state.error}
        </p>
      ) : null}
      {state.uploaded ? (
        <p className="notice ok" role="status">
          {state.uploaded}
        </p>
      ) : null}
    </form>
  );
}

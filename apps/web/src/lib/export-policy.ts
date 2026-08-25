/** Politica pura del proxy de exportacion. No contiene sesiones ni datos. */

export const EXPORT_PROFILE = 'canonical-v1';
export const EXPORT_TIMEOUT_MS = 90_000;
export const MAX_EXPORT_ROWS = 100_000;
export const MAX_EXPORT_BYTES = 96 * 1024 * 1024;

const SAFE_FILENAME =
  /^attachment; filename="fincilia-canonico-[0-9a-f-]{12}\.csv"$/;
const SAFE_SCHEMA = /^[A-Za-z0-9._-]{1,32}$/;
const SAFE_ROW_COUNT = /^(0|[1-9][0-9]{0,5})$/;

export type ExportMetadata = {
  contentType: string;
  contentDisposition: string;
  profile: typeof EXPORT_PROFILE;
  rows: number;
  canonicalSchema: string;
};

export type ExportEligibility = {
  state: string;
  completeness_state: string;
  lineage_state: string;
  manifest: { reproducible: boolean } | null;
};

/** La UI solo ofrece lo mismo que la API aceptara; la API sigue siendo autoridad. */
export function isDatasetExportEligible(
  canExport: boolean,
  dataset: ExportEligibility,
): boolean {
  return (
    canExport &&
    dataset.state === 'published' &&
    dataset.completeness_state === 'verified' &&
    dataset.lineage_state === 'complete' &&
    dataset.manifest?.reproducible === true
  );
}

/**
 * Convierte las cabeceras del API en una lista cerrada. Un nombre de fichero,
 * perfil o conteo inesperado invalida toda la descarga: nunca se refleja una
 * cabecera controlada por otra capa sin comprobarla primero.
 */
export function parseExportMetadata(headers: Headers): ExportMetadata | null {
  const contentType = headers.get('content-type');
  const contentDisposition = headers.get('content-disposition');
  const profile = headers.get('x-fincilia-export-profile');
  const rowsText = headers.get('x-fincilia-export-rows');
  const canonicalSchema = headers.get('x-fincilia-canonical-schema');

  if (
    contentType === null ||
    contentType.split(';', 1)[0]?.trim().toLowerCase() !== 'text/csv' ||
    contentDisposition === null ||
    !SAFE_FILENAME.test(contentDisposition) ||
    profile !== EXPORT_PROFILE ||
    rowsText === null ||
    !SAFE_ROW_COUNT.test(rowsText) ||
    canonicalSchema === null ||
    !SAFE_SCHEMA.test(canonicalSchema)
  ) {
    return null;
  }

  const rows = Number(rowsText);
  if (!Number.isSafeInteger(rows) || rows > MAX_EXPORT_ROWS) {
    return null;
  }

  return {
    contentType,
    contentDisposition,
    profile: EXPORT_PROFILE,
    rows,
    canonicalSchema,
  };
}

export class ExportLimitError extends Error {
  constructor() {
    super('export stream exceeds the configured byte ceiling');
    this.name = 'ExportLimitError';
  }
}

/**
 * Reenvia el cuerpo sin acumularlo y conserva el deadline hasta EOF. El hook
 * finaliza una sola vez tanto al completar como al cancelar o fallar.
 */
export function boundedExportStream(
  source: ReadableStream<Uint8Array>,
  onFinalize: (reason: 'complete' | 'cancelled' | 'failed' | 'too-large') => void,
  maximumBytes = MAX_EXPORT_BYTES,
): ReadableStream<Uint8Array> {
  const reader = source.getReader();
  let bytes = 0;
  let finalized = false;

  const finalize = (
    reason: 'complete' | 'cancelled' | 'failed' | 'too-large',
  ) => {
    if (!finalized) {
      finalized = true;
      onFinalize(reason);
    }
  };

  return new ReadableStream<Uint8Array>(
    {
      async pull(controller) {
        try {
          const { done, value } = await reader.read();
          if (done) {
            finalize('complete');
            controller.close();
            return;
          }
          bytes += value.byteLength;
          if (bytes > maximumBytes) {
            const error = new ExportLimitError();
            finalize('too-large');
            await reader.cancel(error);
            controller.error(error);
            return;
          }
          controller.enqueue(value);
        } catch (error) {
          finalize('failed');
          controller.error(error);
        }
      },
      async cancel(reason) {
        finalize('cancelled');
        await reader.cancel(reason);
      },
    },
    { highWaterMark: 0 },
  );
}

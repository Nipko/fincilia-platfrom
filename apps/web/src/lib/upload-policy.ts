/** Politica pura del proxy de carga. No contiene sesiones ni datos de negocio. */

export const MAX_UPLOAD_FILE_BYTES = 25 * 1024 * 1024;
export const MAX_MULTIPART_OVERHEAD_BYTES = 64 * 1024;
export const MAX_UPLOAD_ENVELOPE_BYTES =
  MAX_UPLOAD_FILE_BYTES + MAX_MULTIPART_OVERHEAD_BYTES;
export const MAX_UPSTREAM_RESPONSE_BYTES = 64 * 1024;
export const UPLOAD_TIMEOUT_MS = 90_000;

const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const MULTIPART = /^multipart\/form-data\s*;(?=.*\bboundary=)[^\r\n]+$/i;
const CONTROL_CHARACTERS = /[\u0000-\u001f\u007f]/g;

export class UploadLimitError extends Error {
  constructor() {
    super('upload envelope exceeds the configured byte ceiling');
    this.name = 'UploadLimitError';
  }
}

export class UpstreamResponseLimitError extends Error {
  constructor() {
    super('upstream response exceeds the configured byte ceiling');
    this.name = 'UpstreamResponseLimitError';
  }
}

export function isUuid(value: string | null | undefined): value is string {
  return typeof value === 'string' && UUID.test(value);
}

export function isMultipart(contentType: string | null): contentType is string {
  return contentType !== null && MULTIPART.test(contentType);
}

export function isAllowedFileSize(byteSize: number): boolean {
  return Number.isSafeInteger(byteSize) && byteSize > 0 && byteSize <= MAX_UPLOAD_FILE_BYTES;
}

/**
 * `null` significa que el transporte no declaro longitud y debe vigilarse al
 * consumir el stream. Valores ambiguos o negativos se rechazan, no se adivinan.
 */
export function parseContentLength(value: string | null): number | null {
  if (value === null) {
    return null;
  }
  if (!/^(0|[1-9][0-9]*)$/.test(value)) {
    throw new TypeError('invalid content-length');
  }
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed)) {
    throw new TypeError('invalid content-length');
  }
  return parsed;
}

/**
 * Exige que el Origin coincida con la autoridad publica que recibio la
 * peticion. En `next start`/standalone, `request.url` puede contener la
 * autoridad interna del contenedor, por lo que la autoridad se toma del Host
 * entrante. No se confia en X-Forwarded-Host. Detras de un proxy con cambio de
 * protocolo se exige `configuredPublicOrigin`.
 */
export function isSameOrigin(
  requestUrl: string,
  origin: string | null,
  host: string | null,
  configuredPublicOrigin: string | null = null,
): boolean {
  if (origin === null || (configuredPublicOrigin === null && host === null)) {
    return false;
  }
  try {
    const supplied = new URL(origin);
    if (
      (supplied.protocol !== 'http:' && supplied.protocol !== 'https:') ||
      supplied.username !== '' ||
      supplied.password !== '' ||
      supplied.pathname !== '/' ||
      supplied.search !== '' ||
      supplied.hash !== ''
    ) {
      return false;
    }
    const expected =
      configuredPublicOrigin ?? `${new URL(requestUrl).protocol}//${host ?? ''}`;
    return supplied.origin === new URL(expected).origin;
  } catch {
    return false;
  }
}

export type CountedStream = {
  stream: ReadableStream<Uint8Array>;
  bytesRead: () => number;
  exceeded: () => boolean;
};

/**
 * Cuenta el cuerpo mientras `fetch` lo consume. Nunca acumula los chunks. El
 * callback permite abortar inmediatamente la llamada upstream al cruzar el
 * techo, incluso cuando `Content-Length` falta o miente.
 */
export function limitStream(
  source: ReadableStream<Uint8Array>,
  maximumBytes: number,
  onExceeded: () => void,
  signal?: AbortSignal,
): CountedStream {
  let bytes = 0;
  let overLimit = false;
  const transformer = new TransformStream<Uint8Array, Uint8Array>({
    transform(chunk, controller) {
      bytes += chunk.byteLength;
      if (bytes > maximumBytes) {
        overLimit = true;
        onExceeded();
        controller.error(new UploadLimitError());
        return;
      }
      controller.enqueue(chunk);
    },
  });
  const stream = signal
    ? source.pipeThrough(transformer, { signal })
    : source.pipeThrough(transformer);
  return {
    stream,
    bytesRead: () => bytes,
    exceeded: () => overLimit,
  };
}

/** Lee solo la pequena respuesta JSON del API con un limite independiente. */
export async function readBoundedJson(
  body: ReadableStream<Uint8Array> | null,
  maximumBytes = MAX_UPSTREAM_RESPONSE_BYTES,
): Promise<unknown> {
  if (body === null) {
    return null;
  }
  const reader = body.getReader();
  const decoder = new TextDecoder('utf-8', { fatal: true });
  let total = 0;
  let text = '';
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      total += value.byteLength;
      if (total > maximumBytes) {
        await reader.cancel();
        throw new UpstreamResponseLimitError();
      }
      text += decoder.decode(value, { stream: true });
    }
    text += decoder.decode();
  } catch (error) {
    // Un UTF-8 invalido puede fallar antes de EOF mientras el productor sigue
    // abierto. Cancelar evita dejar viva una conexion upstream fuera del plazo.
    try {
      await reader.cancel(error);
    } catch {
      // La causa original es la que define la respuesta publica.
    }
    throw error;
  } finally {
    reader.releaseLock();
  }
  return text === '' ? null : (JSON.parse(text) as unknown);
}

export function safeFilename(value: unknown): string {
  if (typeof value !== 'string') {
    return 'sin-nombre';
  }
  const sanitized = value.replace(CONTROL_CHARACTERS, '\uFFFD').trim().slice(0, 255);
  return sanitized || 'sin-nombre';
}

export type SafeArtifact = {
  artifact_id: string;
  filename: string;
  byte_size: number;
  zone: string;
  status: string;
  already_present: boolean;
};

/** Copia solo los campos que la UI necesita; nunca refleja JSON arbitrario. */
export function sanitizeArtifact(value: unknown): SafeArtifact | null {
  if (!value || typeof value !== 'object') {
    return null;
  }
  const record = value as Record<string, unknown>;
  const artifactId =
    typeof record.artifact_id === 'string' ? record.artifact_id : null;
  if (
    !isUuid(artifactId) ||
    typeof record.byte_size !== 'number' ||
    !Number.isSafeInteger(record.byte_size) ||
    record.byte_size < 0 ||
    typeof record.zone !== 'string' ||
    typeof record.status !== 'string' ||
    typeof record.already_present !== 'boolean'
  ) {
    return null;
  }
  return {
    artifact_id: artifactId,
    filename: safeFilename(record.filename),
    byte_size: record.byte_size,
    zone: record.zone.slice(0, 40),
    status: record.status.slice(0, 40),
    already_present: record.already_present,
  };
}

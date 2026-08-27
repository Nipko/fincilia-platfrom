'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { type FormEvent, useRef, useState, useSyncExternalStore } from 'react';

import { isAllowedFileSize } from '@/lib/upload-policy';

type UploadSource = {
  data_source_id: string;
  display_name: string;
  source_family: string;
};

type UploadReply = {
  detail?: unknown;
  next_href?: unknown;
};

const ACCEPTED_EXTENSIONS = '.csv,.pdf,.xlsx,.ods,.zip';
const subscribeToHydration = () => () => undefined;

function safeDetail(value: unknown, fallback: string): string {
  return typeof value === 'string' && value.length <= 240 ? value : fallback;
}

export function UploadForm({
  companyId,
  sources,
  initialSourceId,
}: {
  companyId: string;
  sources: UploadSource[];
  initialSourceId: string;
}) {
  const router = useRouter();
  const controller = useRef<AbortController | null>(null);
  const [sourceId, setSourceId] = useState(initialSourceId);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  // Sin hidratacion no existe el manejador que transmite el stream con limite.
  // Mantener el submit deshabilitado en el HTML inicial evita que una persona
  // rapida haga un GET nativo y pierda silenciosamente el fichero seleccionado.
  const ready = useSyncExternalStore(
    subscribeToHydration,
    () => true,
    () => false,
  );

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setMessage(null);
    const form = event.currentTarget;
    const field = form.elements.namedItem('file');
    const file = field instanceof HTMLInputElement ? field.files?.item(0) : null;
    if (!sourceId) {
      setMessage('Elige la fuente a la que pertenece el documento.');
      return;
    }
    if (!file || file.size === 0) {
      setMessage('Elige un archivo con contenido.');
      return;
    }
    if (!isAllowedFileSize(file.size)) {
      setMessage('El archivo supera el limite de 25 MiB.');
      return;
    }

    const body = new FormData();
    body.append('file', file, file.name);
    const current = new AbortController();
    controller.current = current;
    setPending(true);
    try {
      const response = await fetch(
        `/api/companies/${encodeURIComponent(companyId)}/documents?` +
          new URLSearchParams({ sourceId }).toString(),
        {
          method: 'POST',
          body,
          credentials: 'same-origin',
          headers: { accept: 'application/json' },
          signal: current.signal,
        },
      );
      const reply = (await response.json().catch(() => null)) as UploadReply | null;
      if (response.status === 401) {
        router.push('/entrar');
        return;
      }
      if (!response.ok) {
        setMessage(
          safeDetail(reply?.detail, 'No se pudo completar la carga. Reintenta.'),
        );
        return;
      }
      if (typeof reply?.next_href !== 'string' || !reply.next_href.startsWith('/')) {
        setMessage('La carga termino, pero su confirmacion no fue valida.');
        return;
      }
      router.push(reply.next_href);
      router.refresh();
    } catch (error) {
      setMessage(
        error instanceof DOMException && error.name === 'AbortError'
          ? 'Carga cancelada.'
          : 'No se pudo contactar con Fincilia. Reintenta.',
      );
    } finally {
      controller.current = null;
      setPending(false);
    }
  }

  return (
    <form className="upload" onSubmit={submit} noValidate>
      <label htmlFor="upload-source">
        Fuente del documento
        <select
          id="upload-source"
          value={sourceId}
          onChange={(event) => setSourceId(event.target.value)}
          required
          disabled={pending || sources.length === 0}
        >
          <option value="">elige una fuente activa</option>
          {sources.map((source) => (
            <option key={source.data_source_id} value={source.data_source_id}>
              {source.display_name} · {source.source_family}
            </option>
          ))}
        </select>
      </label>
      {sources.length === 0 ? (
        <p className="notice error" role="status">
          No hay una fuente activa autorizada.{' '}
          <Link href={`/empresas/${companyId}/fuentes`}>Revisar fuentes</Link>
        </p>
      ) : null}
      <label htmlFor="upload-file">
        Extracto o soporte
        <input
          id="upload-file"
          name="file"
          type="file"
          accept={ACCEPTED_EXTENSIONS}
          aria-describedby="upload-limit"
          required
          disabled={pending || sources.length === 0}
        />
      </label>
      <p className="meta" id="upload-limit">
        Maximo 25 MiB. La validacion definitiva se hace mientras se recibe.
      </p>
      <div>
        <button type="submit" disabled={!ready || pending || sources.length === 0}>
          {pending ? 'Subiendo...' : 'Subir'}
        </button>{' '}
        {pending ? (
          <button type="button" onClick={() => controller.current?.abort()}>
            Cancelar
          </button>
        ) : null}
      </div>
      {message ? (
        <p className="notice error" role="alert" aria-live="assertive">
          {message}
        </p>
      ) : null}
    </form>
  );
}

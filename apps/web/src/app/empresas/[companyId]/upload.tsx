'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  type ChangeEvent,
  type FormEvent,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from 'react';

import { isAllowedFileSize } from '@/lib/upload-policy';

type UploadSource = {
  data_source_id: string;
  display_name: string;
  source_family: string;
};

type UploadReply = {
  already_present?: unknown;
  detail?: unknown;
  filename?: unknown;
  next_href?: unknown;
};

type UploadStatus =
  | 'ready'
  | 'uploading'
  | 'uploaded'
  | 'duplicate'
  | 'failed'
  | 'invalid'
  | 'cancelled';

type UploadItem = {
  id: string;
  file: File;
  status: UploadStatus;
  detail: string;
  nextHref: string | null;
};

const ACCEPTED_EXTENSIONS = '.csv,.pdf,.xlsx,.ods,.zip';
export const MAX_BATCH_FILES = 10;
export const MAX_BATCH_BYTES = 100 * 1024 * 1024;
const UPLOAD_CONCURRENCY = 2;
const subscribeToHydration = () => () => undefined;

const STATUS_LABELS: Record<UploadStatus, string> = {
  ready: 'Listo',
  uploading: 'Subiendo',
  uploaded: 'Completado',
  duplicate: 'Ya recibido',
  failed: 'Fallido',
  invalid: 'No valido',
  cancelled: 'Cancelado',
};

function safeDetail(value: unknown, fallback: string): string {
  return typeof value === 'string' && value.length <= 240 ? value : fallback;
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value.toLocaleString('es-CO')} B`;
  if (value < 1024 * 1024) {
    return `${(value / 1024).toLocaleString('es-CO', {
      maximumFractionDigits: 1,
    })} KiB`;
  }
  return `${(value / (1024 * 1024)).toLocaleString('es-CO', {
    maximumFractionDigits: 1,
  })} MiB`;
}

function makeItem(file: File, index: number, acceptedBytes: number): UploadItem {
  const id = `${index}-${file.name}-${file.size}-${file.lastModified}`;
  if (index >= MAX_BATCH_FILES) {
    return {
      id, file, status: 'invalid', nextHref: null,
      detail: `El lote admite maximo ${MAX_BATCH_FILES} archivos.`,
    };
  }
  if (!file.name.trim()) {
    return {
      id, file, status: 'invalid', nextHref: null,
      detail: 'El archivo no tiene un nombre valido.',
    };
  }
  if (file.size === 0) {
    return {
      id, file, status: 'invalid', nextHref: null,
      detail: 'El archivo no tiene contenido.',
    };
  }
  if (!isAllowedFileSize(file.size)) {
    return {
      id, file, status: 'invalid', nextHref: null,
      detail: 'El archivo supera el limite de 25 MiB.',
    };
  }
  if (acceptedBytes + file.size > MAX_BATCH_BYTES) {
    return {
      id, file, status: 'invalid', nextHref: null,
      detail: 'Supera el limite acumulado de 100 MiB por lote.',
    };
  }
  return {
    id, file, status: 'ready', nextHref: null,
    detail: 'Preparado para enviar.',
  };
}

export function prepareUploadItems(files: readonly File[]): UploadItem[] {
  let acceptedBytes = 0;
  return files.map((file, index) => {
    const item = makeItem(file, index, acceptedBytes);
    if (item.status === 'ready') acceptedBytes += file.size;
    return item;
  });
}

function isSafeDocumentHref(href: unknown, companyId: string): href is string {
  const prefix = `/empresas/${encodeURIComponent(companyId)}/documentos/`;
  return typeof href === 'string' && href.startsWith(prefix) && !href.startsWith('//');
}

function statusClass(status: UploadStatus): string {
  if (status === 'uploaded' || status === 'duplicate') return 'ok';
  if (status === 'failed' || status === 'invalid') return 'denied';
  return '';
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
  const controllers = useRef(new Map<string, AbortController>());
  const cancelRequested = useRef(false);
  const fileInput = useRef<HTMLInputElement | null>(null);
  const [sourceId, setSourceId] = useState(initialSourceId);
  const [items, setItems] = useState<UploadItem[]>([]);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  // Sin hidratacion no existe el manejador que transmite cada stream con limite.
  // Mantener el submit deshabilitado en el HTML inicial evita un GET nativo.
  const ready = useSyncExternalStore(
    subscribeToHydration,
    () => true,
    () => false,
  );

  const counts = useMemo(() => {
    const result: Record<UploadStatus, number> = {
      ready: 0, uploading: 0, uploaded: 0, duplicate: 0,
      failed: 0, invalid: 0, cancelled: 0,
    };
    for (const item of items) result[item.status] += 1;
    return result;
  }, [items]);

  function patchItem(id: string, patch: Partial<UploadItem>): void {
    setItems((current) => current.map((item) => (
      item.id === id ? { ...item, ...patch } : item
    )));
  }

  function selectFiles(event: ChangeEvent<HTMLInputElement>): void {
    const selected = Array.from(event.currentTarget.files ?? []);
    const next = prepareUploadItems(selected);
    setItems(next);
    const invalid = next.find((item) => item.status === 'invalid');
    const hasReady = next.some((item) => item.status === 'ready');
    setMessage(invalid
      ? (hasReady
        ? 'Revisa los archivos marcados. Los validos si se pueden enviar.'
        : invalid.detail)
      : null);
  }

  function clearQueue(): void {
    setItems([]);
    setMessage(null);
    if (fileInput.current) fileInput.current.value = '';
  }

  function cancelBatch(): void {
    cancelRequested.current = true;
    for (const controller of controllers.current.values()) controller.abort();
    setItems((current) => current.map((item) => (
      item.status === 'ready' || item.status === 'uploading'
        ? { ...item, status: 'cancelled', detail: 'No se envio por cancelacion.' }
        : item
    )));
  }

  async function runBatch(statuses: readonly UploadStatus[]): Promise<void> {
    if (pending) return;
    setMessage(null);
    if (!sourceId) {
      setMessage('Elige la fuente a la que pertenecen los documentos.');
      return;
    }
    const selected = items.filter((item) => statuses.includes(item.status));
    if (selected.length === 0) {
      setMessage(
        items.find((item) => item.status === 'invalid')?.detail
          ?? 'Elige al menos un archivo valido para enviar.',
      );
      return;
    }

    cancelRequested.current = false;
    setPending(true);
    let nextIndex = 0;
    let authenticationExpired = false;
    const successfulHrefs: string[] = [];

    const uploadOne = async (item: UploadItem): Promise<void> => {
      const current = new AbortController();
      controllers.current.set(item.id, current);
      patchItem(item.id, {
        status: 'uploading', detail: 'Enviando y verificando el documento.',
        nextHref: null,
      });
      try {
        const body = new FormData();
        body.append('file', item.file, item.file.name);
        const response = await fetch(
          `/api/companies/${encodeURIComponent(companyId)}/documents?` +
            new URLSearchParams({ sourceId }).toString(),
          {
            method: 'POST', body, credentials: 'same-origin',
            headers: { accept: 'application/json' }, signal: current.signal,
          },
        );
        const reply = (await response.json().catch(() => null)) as UploadReply | null;
        if (response.status === 401) {
          authenticationExpired = true;
          cancelRequested.current = true;
          for (const controller of controllers.current.values()) {
            if (controller !== current) controller.abort();
          }
          patchItem(item.id, {
            status: 'failed', detail: 'La sesion vencio. Vuelve a ingresar.',
          });
          return;
        }
        if (!response.ok) {
          patchItem(item.id, {
            status: 'failed',
            detail: safeDetail(
              reply?.detail,
              'No se pudo completar la carga. Puedes reintentar este archivo.',
            ),
          });
          return;
        }
        if (!isSafeDocumentHref(reply?.next_href, companyId)) {
          patchItem(item.id, {
            status: 'failed',
            detail: 'La carga termino, pero su confirmacion no fue valida.',
          });
          return;
        }
        successfulHrefs.push(reply.next_href);
        patchItem(item.id, {
          status: reply?.already_present === true ? 'duplicate' : 'uploaded',
          detail: reply?.already_present === true
            ? 'Esta recepcion ya existia en la misma fuente.'
            : 'Recepcion confirmada.',
          nextHref: reply.next_href,
        });
      } catch (error) {
        patchItem(item.id, {
          status: error instanceof DOMException && error.name === 'AbortError'
            ? 'cancelled'
            : 'failed',
          detail: error instanceof DOMException && error.name === 'AbortError'
            ? 'No se envio por cancelacion.'
            : 'No se pudo contactar con Fincilia. Puedes reintentar.',
        });
      } finally {
        controllers.current.delete(item.id);
      }
    };

    const worker = async () => {
      while (!cancelRequested.current) {
        const index = nextIndex;
        nextIndex += 1;
        const item = selected[index];
        if (!item) return;
        await uploadOne(item);
      }
    };

    await Promise.all(
      Array.from(
        { length: Math.min(UPLOAD_CONCURRENCY, selected.length) },
        () => worker(),
      ),
    );
    if (cancelRequested.current) {
      const pendingIds = new Set(selected.slice(nextIndex).map((item) => item.id));
      setItems((currentItems) => currentItems.map((item) => (
        pendingIds.has(item.id) && statuses.includes(item.status)
          ? { ...item, status: 'cancelled', detail: 'No se envio por cancelacion.' }
          : item
      )));
    }
    setPending(false);

    if (authenticationExpired) {
      router.push('/entrar');
      return;
    }
    const initialSingle = statuses.length === 1
      && statuses[0] === 'ready'
      && selected.length === 1
      && items.length === 1;
    if (initialSingle && successfulHrefs.length === 1) {
      router.push(successfulHrefs[0]!);
      router.refresh();
      return;
    }
    if (successfulHrefs.length > 0) router.refresh();
  }

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    await runBatch(['ready']);
  }

  const retryable = counts.failed + counts.cancelled;
  const finished = counts.uploaded + counts.duplicate;

  return (
    <form className="upload upload-batch" onSubmit={submit} noValidate>
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
          ref={fileInput}
          id="upload-file"
          name="file"
          type="file"
          accept={ACCEPTED_EXTENSIONS}
          aria-describedby={items.length > 0 ? 'upload-limit upload-summary' : 'upload-limit'}
          required
          multiple
          onChange={selectFiles}
          disabled={pending || sources.length === 0}
        />
      </label>
      <p className="meta" id="upload-limit">
        Hasta 10 archivos, 25 MiB por archivo y 100 MiB por lote. Cada documento
        se confirma por separado. CSV, XLSX, ODS y PDF con texto embebido seguro
        se procesan. PDF escaneado solicita OCR y ZIP generico queda en cuarentena.
      </p>

      {items.length > 0 ? (
        <section className="upload-queue" aria-labelledby="upload-queue-title">
          <div className="upload-queue-heading">
            <h3 id="upload-queue-title">Bandeja de carga</h3>
            {!pending ? (
              <button className="quiet" type="button" onClick={clearQueue}>
                Quitar lista
              </button>
            ) : null}
          </div>
          <p className="meta" id="upload-summary" role="status" aria-live="polite">
            {items.length} seleccionado(s) · {counts.ready} listo(s) · {finished}{' '}
            confirmado(s) · {counts.failed} fallido(s) · {counts.invalid} no valido(s)
          </p>
          <ol className="upload-items">
            {items.map((item) => (
              <li key={item.id}>
                <div>
                  <strong>{item.file.name || 'Archivo sin nombre'}</strong>
                  <span className="meta">{formatBytes(item.file.size)}</span>
                  <span className="meta">{item.detail}</span>
                </div>
                <div className="upload-item-result">
                  <span className={`outcome ${statusClass(item.status)}`}>
                    {STATUS_LABELS[item.status]}
                  </span>
                  {item.nextHref ? <Link href={item.nextHref}>Abrir</Link> : null}
                </div>
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      <div className="upload-actions">
        <button
          type="submit"
          disabled={!ready || pending || sources.length === 0 || items.length === 0}
        >
          {pending
            ? 'Cargando lote...'
            : counts.ready > 1 ? `Subir ${counts.ready}` : 'Subir'}
        </button>{' '}
        {pending ? (
          <button className="quiet" type="button" onClick={cancelBatch}>
            Cancelar lote
          </button>
        ) : retryable > 0 ? (
          <button
            className="quiet"
            type="button"
            onClick={() => void runBatch(['failed', 'cancelled'])}
          >
            Reintentar {retryable}
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

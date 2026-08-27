import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { MAX_UPLOAD_FILE_BYTES } from '@/lib/upload-policy';

const router = vi.hoisted(() => ({ push: vi.fn(), refresh: vi.fn() }));
vi.mock('next/navigation', () => ({ useRouter: () => router }));

import {
  MAX_BATCH_BYTES,
  MAX_BATCH_FILES,
  UploadForm,
  prepareUploadItems,
} from '../upload';

const COMPANY_ID = '5f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5e';
const SOURCE_A = '6f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5f';
const SOURCE_B = '7f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d60';
const ARTIFACT = '8f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d61';
const SOURCES = [
  { data_source_id: SOURCE_A, display_name: 'Banco sintetico A', source_family: 'bank' },
  { data_source_id: SOURCE_B, display_name: 'Banco sintetico B', source_family: 'bank' },
];

describe('UploadForm', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it('no elige la primera fuente y envia solo la elegida visiblemente', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(async (..._arguments: unknown[]) => ({
      ok: true,
      status: 200,
      json: async () => ({
        next_href:
          `/empresas/${COMPANY_ID}/documentos/${ARTIFACT}?fuente=${SOURCE_B}`,
      }),
    }));
    vi.stubGlobal('fetch', fetchMock);
    render(
      <UploadForm companyId={COMPANY_ID} sources={SOURCES} initialSourceId="" />,
    );

    const file = new File(['fecha,importe\n2026-01-01,1.00'], 'sintetico.csv', {
      type: 'text/csv',
    });
    await user.upload(screen.getByLabelText('Extracto o soporte'), file);
    await user.click(screen.getByRole('button', { name: 'Subir' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Elige la fuente');
    expect(fetchMock).not.toHaveBeenCalled();

    await user.selectOptions(screen.getByLabelText('Fuente del documento'), SOURCE_B);
    await user.click(screen.getByRole('button', { name: 'Subir' }));

    expect(fetchMock).toHaveBeenCalledOnce();
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(`sourceId=${SOURCE_B}`);
    expect(String(fetchMock.mock.calls[0]?.[0])).not.toContain(`sourceId=${SOURCE_A}`);
    expect(router.push).toHaveBeenCalledWith(
      `/empresas/${COMPANY_ID}/documentos/${ARTIFACT}?fuente=${SOURCE_B}`,
    );
  });

  it('rechaza 25 MiB mas un byte antes de abrir la red', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    render(
      <UploadForm
        companyId={COMPANY_ID}
        sources={SOURCES}
        initialSourceId={SOURCE_A}
      />,
    );
    const file = new File(['x'], 'demasiado-grande.csv', { type: 'text/csv' });
    Object.defineProperty(file, 'size', { value: MAX_UPLOAD_FILE_BYTES + 1 });

    await user.upload(screen.getByLabelText('Extracto o soporte'), file);
    await user.click(screen.getByRole('button', { name: 'Subir' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('limite de 25 MiB');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('limita cantidad y volumen acumulado sin reservar memoria adicional', () => {
    const eleven = Array.from({ length: MAX_BATCH_FILES + 1 }, (_, index) =>
      new File(['x'], `sintetico-${index}.csv`, { type: 'text/csv' }));
    const byCount = prepareUploadItems(eleven);
    expect(byCount.filter((item) => item.status === 'ready')).toHaveLength(10);
    expect(byCount.at(-1)).toMatchObject({
      status: 'invalid', detail: expect.stringContaining('maximo 10'),
    });

    const byVolume = Array.from({ length: 5 }, (_, index) => {
      const file = new File(['x'], `volumen-${index}.csv`, { type: 'text/csv' });
      Object.defineProperty(file, 'size', { value: MAX_BATCH_BYTES / 4 });
      return file;
    });
    const prepared = prepareUploadItems(byVolume);
    expect(prepared.filter((item) => item.status === 'ready')).toHaveLength(4);
    expect(prepared.at(-1)).toMatchObject({
      status: 'invalid', detail: expect.stringContaining('100 MiB'),
    });
  });

  it('carga un lote con maximo dos requests en vuelo y conserva sus expedientes', async () => {
    const user = userEvent.setup();
    let active = 0;
    let maximum = 0;
    let sequence = 0;
    const fetchMock = vi.fn(async (_url: unknown) => {
      active += 1;
      maximum = Math.max(maximum, active);
      await new Promise((resolve) => setTimeout(resolve, 10));
      active -= 1;
      sequence += 1;
      return {
        ok: true,
        status: 200,
        json: async () => ({
          next_href:
            `/empresas/${COMPANY_ID}/documentos/` +
            `8f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d6${sequence}`,
          already_present: false,
        }),
      };
    });
    vi.stubGlobal('fetch', fetchMock);
    render(
      <UploadForm
        companyId={COMPANY_ID}
        sources={SOURCES}
        initialSourceId={SOURCE_A}
      />,
    );
    const files = ['uno', 'dos', 'tres'].map((name) =>
      new File([`fecha,importe\n2026-01-01,${name}`], `${name}.csv`, {
        type: 'text/csv',
      }));

    await user.upload(screen.getByLabelText('Extracto o soporte'), files);
    await user.click(screen.getByRole('button', { name: 'Subir 3' }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    await waitFor(() => expect(screen.getAllByText('Completado')).toHaveLength(3));
    expect(maximum).toBe(2);
    expect(router.push).not.toHaveBeenCalled();
    expect(router.refresh).toHaveBeenCalledOnce();
    expect(screen.getAllByRole('link', { name: 'Abrir' })).toHaveLength(3);
    for (const call of fetchMock.mock.calls) {
      expect(String(call[0])).toContain(`sourceId=${SOURCE_A}`);
    }
  });

  it('reintenta solo el archivo fallido sin repetir el ya confirmado', async () => {
    const user = userEvent.setup();
    const attempts = new Map<string, number>();
    const fetchMock = vi.fn(async (_url: unknown, init?: RequestInit) => {
      const file = (init?.body as FormData).get('file') as File;
      const count = (attempts.get(file.name) ?? 0) + 1;
      attempts.set(file.name, count);
      if (file.name === 'dos.csv' && count === 1) {
        return {
          ok: false, status: 503,
          json: async () => ({ detail: 'Servicio temporalmente no disponible.' }),
        };
      }
      const suffix = file.name === 'uno.csv' ? '1' : '2';
      return {
        ok: true, status: 200,
        json: async () => ({
          next_href:
            `/empresas/${COMPANY_ID}/documentos/` +
            `8f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d6${suffix}`,
        }),
      };
    });
    vi.stubGlobal('fetch', fetchMock);
    render(
      <UploadForm companyId={COMPANY_ID} sources={SOURCES} initialSourceId={SOURCE_A} />,
    );
    await user.upload(screen.getByLabelText('Extracto o soporte'), [
      new File(['uno'], 'uno.csv', { type: 'text/csv' }),
      new File(['dos'], 'dos.csv', { type: 'text/csv' }),
    ]);
    await user.click(screen.getByRole('button', { name: 'Subir 2' }));

    expect(await screen.findByText('Fallido')).toBeInTheDocument();
    expect(screen.getByText('Completado')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Reintentar 1' }));

    await waitFor(() => expect(screen.getAllByText('Completado')).toHaveLength(2));
    expect(attempts.get('uno.csv')).toBe(1);
    expect(attempts.get('dos.csv')).toBe(2);
    expect(router.push).not.toHaveBeenCalled();
    expect(router.refresh).toHaveBeenCalledTimes(2);
  });

  it('cancelar aborta las dos cargas activas y no inicia la tercera', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn((_url: unknown, init?: RequestInit) =>
      new Promise((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => {
          reject(new DOMException('cancelled', 'AbortError'));
        }, { once: true });
      }));
    vi.stubGlobal('fetch', fetchMock);
    render(
      <UploadForm companyId={COMPANY_ID} sources={SOURCES} initialSourceId={SOURCE_A} />,
    );
    await user.upload(screen.getByLabelText('Extracto o soporte'), [
      new File(['uno'], 'uno.csv'),
      new File(['dos'], 'dos.csv'),
      new File(['tres'], 'tres.csv'),
    ]);
    await user.click(screen.getByRole('button', { name: 'Subir 3' }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    await user.click(screen.getByRole('button', { name: 'Cancelar lote' }));

    await waitFor(() => expect(screen.getAllByText('Cancelado')).toHaveLength(3));
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(router.push).not.toHaveBeenCalled();
    expect(router.refresh).not.toHaveBeenCalled();
  });

  it('una sesion vencida detiene el lote y vuelve a ingreso', async () => {
    const user = userEvent.setup();
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: false, status: 401,
      json: async () => ({ detail: 'La sesion vencio.' }),
    })));
    render(
      <UploadForm companyId={COMPANY_ID} sources={SOURCES} initialSourceId={SOURCE_A} />,
    );
    await user.upload(
      screen.getByLabelText('Extracto o soporte'),
      new File(['uno'], 'uno.csv'),
    );
    await user.click(screen.getByRole('button', { name: 'Subir' }));

    await waitFor(() => expect(router.push).toHaveBeenCalledWith('/entrar'));
    expect(router.refresh).not.toHaveBeenCalled();
  });
});

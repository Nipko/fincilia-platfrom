import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { MAX_UPLOAD_FILE_BYTES } from '@/lib/upload-policy';

const router = vi.hoisted(() => ({ push: vi.fn(), refresh: vi.fn() }));
vi.mock('next/navigation', () => ({ useRouter: () => router }));

import { UploadForm } from '../upload';

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
});

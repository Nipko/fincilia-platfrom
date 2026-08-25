import { describe, expect, it, vi } from 'vitest';

import {
  ExportLimitError,
  boundedExportStream,
  parseExportMetadata,
} from '../export-policy';

function headers(overrides: Record<string, string> = {}): Headers {
  return new Headers({
    'content-type': 'text/csv; charset=utf-8',
    'content-disposition':
      'attachment; filename="fincilia-canonico-6f0f7b18-0a7.csv"',
    'x-fincilia-export-profile': 'canonical-v1',
    'x-fincilia-export-rows': '2',
    'x-fincilia-canonical-schema': 'v1.0',
    ...overrides,
  });
}

describe('export policy', () => {
  it('acepta solo el contrato cerrado de cabeceras', () => {
    expect(parseExportMetadata(headers())).toEqual({
      contentType: 'text/csv; charset=utf-8',
      contentDisposition:
        'attachment; filename="fincilia-canonico-6f0f7b18-0a7.csv"',
      profile: 'canonical-v1',
      rows: 2,
      canonicalSchema: 'v1.0',
    });
  });

  it.each([
    ['content-type', 'application/json'],
    ['content-disposition', 'attachment; filename="extracto-cliente.csv"'],
    ['content-disposition', 'attachment; filename="fincilia-canonico-bad.csv"; size=9'],
    ['x-fincilia-export-profile', 'latest'],
    ['x-fincilia-export-rows', '100001'],
    ['x-fincilia-export-rows', '02'],
    ['x-fincilia-canonical-schema', '../v1'],
  ])('rechaza %s inesperado', (name, value) => {
    expect(parseExportMetadata(headers({ [name]: value }))).toBeNull();
  });

  it('transmite por chunks sin acumular y finaliza una sola vez', async () => {
    const finalized = vi.fn();
    const source = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode('uno,'));
        controller.enqueue(new TextEncoder().encode('dos'));
        controller.close();
      },
    });

    const result = await new Response(
      boundedExportStream(source, finalized, 32),
    ).text();

    expect(result).toBe('uno,dos');
    expect(finalized).toHaveBeenCalledOnce();
    expect(finalized).toHaveBeenCalledWith('complete');
  });

  it('cancela la fuente al cruzar el techo durante el stream', async () => {
    const finalized = vi.fn();
    const cancelled = vi.fn();
    const source = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new Uint8Array(5));
      },
      cancel: cancelled,
    });
    const reader = boundedExportStream(source, finalized, 4).getReader();

    await expect(reader.read()).rejects.toBeInstanceOf(ExportLimitError);
    expect(cancelled).toHaveBeenCalledOnce();
    expect(finalized).toHaveBeenCalledWith('too-large');
  });
});

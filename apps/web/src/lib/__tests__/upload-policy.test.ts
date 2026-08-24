import { describe, expect, it, vi } from 'vitest';

import {
  MAX_UPLOAD_ENVELOPE_BYTES,
  MAX_UPLOAD_FILE_BYTES,
  UpstreamResponseLimitError,
  isAllowedFileSize,
  isMultipart,
  isSameOrigin,
  isUuid,
  limitStream,
  parseContentLength,
  readBoundedJson,
  safeFilename,
  sanitizeArtifact,
} from '../upload-policy';

function byteStream(sizes: number[]): ReadableStream<Uint8Array> {
  return new ReadableStream({
    pull(controller) {
      const size = sizes.shift();
      if (size === undefined) {
        controller.close();
        return;
      }
      controller.enqueue(new Uint8Array(size));
    },
  });
}

async function consume(stream: ReadableStream<Uint8Array>): Promise<number> {
  const reader = stream.getReader();
  let total = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      return total;
    }
    total += value.byteLength;
  }
}

describe('upload size policy', () => {
  it('acepta exactamente 25 MiB de archivo y rechaza un byte adicional', () => {
    expect(isAllowedFileSize(MAX_UPLOAD_FILE_BYTES)).toBe(true);
    expect(isAllowedFileSize(MAX_UPLOAD_FILE_BYTES + 1)).toBe(false);
    expect(isAllowedFileSize(0)).toBe(false);
  });

  it('transmite el sobre maximo sin acumularlo', async () => {
    const onExceeded = vi.fn();
    const counted = limitStream(
      byteStream([MAX_UPLOAD_FILE_BYTES, MAX_UPLOAD_ENVELOPE_BYTES - MAX_UPLOAD_FILE_BYTES]),
      MAX_UPLOAD_ENVELOPE_BYTES,
      onExceeded,
    );
    await expect(consume(counted.stream)).resolves.toBe(MAX_UPLOAD_ENVELOPE_BYTES);
    expect(counted.bytesRead()).toBe(MAX_UPLOAD_ENVELOPE_BYTES);
    expect(counted.exceeded()).toBe(false);
    expect(onExceeded).not.toHaveBeenCalled();
  });

  it('corta un stream sin longitud declarada al cruzar el techo', async () => {
    const onExceeded = vi.fn();
    const counted = limitStream(
      byteStream([MAX_UPLOAD_ENVELOPE_BYTES, 1]),
      MAX_UPLOAD_ENVELOPE_BYTES,
      onExceeded,
    );
    await expect(consume(counted.stream)).rejects.toThrow(/byte ceiling/);
    expect(counted.bytesRead()).toBe(MAX_UPLOAD_ENVELOPE_BYTES + 1);
    expect(counted.exceeded()).toBe(true);
    expect(onExceeded).toHaveBeenCalledOnce();
  });

  it('cancela el stream fuente cuando aborta la operacion de carga', async () => {
    const cancelled = vi.fn();
    const source = new ReadableStream<Uint8Array>({
      pull(controller) {
        controller.enqueue(new Uint8Array([1]));
      },
      cancel: cancelled,
    });
    const abort = new AbortController();
    const counted = limitStream(source, 1024, vi.fn(), abort.signal);
    const reader = counted.stream.getReader();
    await expect(reader.read()).resolves.toMatchObject({ done: false });

    abort.abort(new Error('synthetic-cancel'));

    await expect(reader.read()).rejects.toThrow('synthetic-cancel');
    await vi.waitFor(() => expect(cancelled).toHaveBeenCalledOnce());
  });
});

describe('request validation', () => {
  it('rechaza longitudes ambiguas, negativas o fuera de entero seguro', () => {
    expect(parseContentLength(null)).toBeNull();
    expect(parseContentLength('0')).toBe(0);
    expect(parseContentLength('42')).toBe(42);
    for (const value of ['-1', '+1', '01', '1, 2', '1.5', '9007199254740992']) {
      expect(() => parseContentLength(value)).toThrow('invalid content-length');
    }
  });

  it('exige multipart con boundary y origen exacto', () => {
    expect(isMultipart('multipart/form-data; boundary=synthetic')).toBe(true);
    expect(isMultipart('multipart/form-data')).toBe(false);
    expect(isMultipart('application/json')).toBe(false);
    expect(
      isSameOrigin('http://0.0.0.0:3000/ruta', 'http://127.0.0.1:53000', '127.0.0.1:53000'),
    ).toBe(true);
    expect(isSameOrigin('https://fincilia.test/ruta', null, 'fincilia.test')).toBe(false);
    expect(
      isSameOrigin('https://fincilia.test/ruta', 'https://evil.test', 'fincilia.test'),
    ).toBe(false);
    expect(
      isSameOrigin(
        'http://web:3000/ruta',
        'https://fincilia.example',
        'web:3000',
        'https://fincilia.example',
      ),
    ).toBe(true);
    expect(
      isSameOrigin('https://fincilia.test/ruta', 'https://fincilia.test/path', 'fincilia.test'),
    ).toBe(false);
  });

  it('acepta UUID reales y no identificadores inventados', () => {
    expect(isUuid('5f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5e')).toBe(true);
    expect(isUuid('../fuente')).toBe(false);
    expect(isUuid('00000000-0000-0000-0000-000000000000')).toBe(false);
  });
});

describe('bounded upstream response', () => {
  it('lee JSON pequeno y cancela una respuesta que excede el techo', async () => {
    const encoded = new TextEncoder().encode('{"ok":true}');
    const jsonStream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoded);
        controller.close();
      },
    });
    await expect(readBoundedJson(jsonStream, 32)).resolves.toEqual({ ok: true });

    const oversized = readBoundedJson(byteStream([33]), 32);
    await expect(oversized).rejects.toBeInstanceOf(UpstreamResponseLimitError);
  });

  it('cancela un upstream abierto si falla la decodificacion UTF-8', async () => {
    const cancel = vi.fn();
    const malformed = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new Uint8Array([0xff]));
      },
      cancel,
    });

    await expect(readBoundedJson(malformed, 32)).rejects.toThrow();
    expect(cancel).toHaveBeenCalledOnce();
  });

  it('sanea el nombre y copia solo el contrato permitido', () => {
    expect(safeFilename('  reporte\u0000\n.csv  ')).toBe('reporte\uFFFD\uFFFD.csv');
    expect(
      sanitizeArtifact({
        artifact_id: '5f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5e',
        filename: 'sintetico.csv',
        byte_size: 12,
        zone: 'quarantine',
        status: 'quarantined',
        already_present: false,
        secret: 'no debe reflejarse',
      }),
    ).toEqual({
      artifact_id: '5f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5e',
      filename: 'sintetico.csv',
      byte_size: 12,
      zone: 'quarantine',
      status: 'quarantined',
      already_present: false,
    });
  });
});

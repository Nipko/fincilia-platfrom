import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('server-only', () => ({}));
vi.mock('@/lib/server-config', () => ({
  apiUrl: (path: string) => `http://api.internal${path}`,
}));

import { fetchMe } from '../api';

describe('API response deadline', () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('mantiene el timeout hasta consumir el cuerpo JSON', async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_input: unknown, init?: RequestInit) => {
        const signal = init?.signal;
        const body = new ReadableStream<Uint8Array>({
          start(controller) {
            signal?.addEventListener(
              'abort',
              () => controller.error(new DOMException('aborted', 'AbortError')),
              { once: true },
            );
          },
        });
        return new Response(body, {
          status: 200,
          headers: { 'content-type': 'application/json' },
        });
      }),
    );

    const assertion = expect(fetchMe('token-sintetico')).rejects.toMatchObject({
      status: 503,
    });
    await vi.advanceTimersByTimeAsync(8_001);
    await assertion;
  });
});

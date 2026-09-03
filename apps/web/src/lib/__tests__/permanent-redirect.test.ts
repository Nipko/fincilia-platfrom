import { describe, expect, it } from 'vitest';

import { permanentRedirectResponse } from '../permanent-redirect';

describe('permanentRedirectResponse', () => {
  it('returns an empty permanent redirect to the supplied local path', async () => {
    const response = permanentRedirectResponse('/privacy');

    expect(response.status).toBe(308);
    expect(response.headers.get('location')).toBe('/privacy');
    expect(await response.text()).toBe('');
  });

  it.each(['https://example.invalid', '//example.invalid'])(
    'rejects a non-local destination: %s',
    (destination) => {
      expect(() => permanentRedirectResponse(destination)).toThrow(
        'permanent redirects must target an absolute local path',
      );
    },
  );
});

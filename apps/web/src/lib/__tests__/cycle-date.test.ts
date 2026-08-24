import { describe, expect, it } from 'vitest';

import { isoDateInTimeZone } from '../cycle-date';

describe('isoDateInTimeZone', () => {
  it('conserva el dia civil de Bogota cuando UTC ya salto al siguiente', () => {
    const instant = new Date('2026-09-01T02:30:00.000Z');

    expect(isoDateInTimeZone('America/Bogota', instant)).toBe('2026-08-31');
    expect(isoDateInTimeZone('UTC', instant)).toBe('2026-09-01');
  });
});

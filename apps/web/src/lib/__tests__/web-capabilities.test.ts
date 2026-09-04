import { describe, expect, it } from 'vitest';

import {
  DOCUMENT_FORMAT_CAPABILITIES,
  QUALITY_RULE_COVERAGE,
  formatBytes,
  formatLimit,
  formatMinorAmount,
  summarizeDeliveries,
  usagePercent,
} from '../web-capabilities';

describe('web capabilities', () => {
  it('mantiene formatos y reglas sin duplicados', () => {
    expect(new Set(DOCUMENT_FORMAT_CAPABILITIES.map((item) => item.id)).size).toBe(4);
    expect(new Set(QUALITY_RULE_COVERAGE.map((item) => item.code)).size).toBe(13);
    expect(DOCUMENT_FORMAT_CAPABILITIES.find((item) => item.id === 'pdf')?.boundary)
      .toMatch(/OCR requerido/);
  });

  it('resume estados sin convertir suprimidos en entregados', () => {
    expect(summarizeDeliveries([
      { status: 'suppressed' }, { status: 'suppressed' }, { status: 'failed' },
    ])).toEqual({ queued: 0, sent: 0, delivered: 0, failed: 1, suppressed: 2 });
  });

  it('formatea capacidad y porcentajes de forma acotada', () => {
    expect(formatBytes(2048)).toMatch(/2/);
    expect(formatBytes(-1)).toBe('—');
    expect(formatLimit(null, 'documentos')).toBe('Sin límite publicado');
    expect(formatMinorAmount(125000, 'USD')).toMatch(/1[.,]250/);
    expect(formatMinorAmount(-1, 'USD')).toBe('—');
    expect(usagePercent(75, 100)).toBe(75);
    expect(usagePercent(150, 100)).toBe(100);
    expect(usagePercent(1, null)).toBeNull();
  });
});

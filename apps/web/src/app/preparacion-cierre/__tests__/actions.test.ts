import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  readSession: vi.fn(), prepare: vi.fn(), decide: vi.fn(),
  revalidatePath: vi.fn(),
  redirect: vi.fn((): never => { throw new Error('NEXT_REDIRECT'); }),
}));

vi.mock('server-only', () => ({}));
vi.mock('next/cache', () => ({ revalidatePath: mocks.revalidatePath }));
vi.mock('next/navigation', () => ({ redirect: mocks.redirect }));
vi.mock('@/lib/session', () => ({ readSession: mocks.readSession }));
vi.mock('@/lib/api', async (importOriginal) => ({
  ...await importOriginal<typeof import('@/lib/api')>(),
  prepareCloseReviewPacket: mocks.prepare,
  decideCloseReviewPacket: mocks.decide,
}));

import { ApiError } from '@/lib/api';
import { decideCloseReviewAction, prepareCloseReviewAction } from '../actions';

const COMPANY = '161b0037-c445-50aa-b400-72632d3f53f0';
const REVIEWER = '21111111-1111-4111-8111-111111111111';
const PACKET = '31111111-1111-4111-8111-111111111111';
const INITIAL = { error: null, done: null };

function form(values: Record<string, string>): FormData {
  const data = new FormData();
  for (const [key, value] of Object.entries(values)) data.set(key, value);
  return data;
}

describe('acciones de expediente previo al cierre', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.readSession.mockResolvedValue({ token: 'synthetic-token' });
  });

  it('rechaza entradas abiertas antes de llamar a la API', async () => {
    const result = await prepareCloseReviewAction(INITIAL, form({
      companyId: '../foreign', periodStart: '2026-07-01', periodEnd: '2026-07-31',
      reviewerId: REVIEWER, idempotencyKey: 'cls005-safe-command-01',
    }));
    expect(result.error).toMatch(/validos/i);
    expect(mocks.prepare).not.toHaveBeenCalled();
  });

  it('prepara con identificadores cerrados y no duplica un replay', async () => {
    mocks.prepare.mockResolvedValue({ version: 3, replayed: true });
    const result = await prepareCloseReviewAction(INITIAL, form({
      companyId: COMPANY, periodStart: '2026-07-01', periodEnd: '2026-07-31',
      reviewerId: REVIEWER, idempotencyKey: 'cls005-safe-command-02',
    }));
    expect(mocks.prepare).toHaveBeenCalledWith(
      'synthetic-token', COMPANY, 'cls005-safe-command-02', {
        period_start: '2026-07-01', period_end: '2026-07-31',
        assigned_reviewer_id: REVIEWER,
      });
    expect(result.done).toMatch(/no se duplico/i);
    expect(mocks.revalidatePath).toHaveBeenCalledWith('/preparacion-cierre');
  });

  it('acepta solo pares cerrados de decision y motivo', async () => {
    const result = await decideCloseReviewAction(INITIAL, form({
      companyId: COMPANY, packetId: PACKET,
      idempotencyKey: 'cls005-safe-command-03',
      decision: 'evidence_reviewed', reasonCode: 'missing_evidence',
    }));
    expect(result.error).toMatch(/decision.*motivo/i);
    expect(mocks.decide).not.toHaveBeenCalled();
  });

  it('registra cambios sin afirmar efecto de cierre', async () => {
    mocks.decide.mockResolvedValue({ replayed: false });
    const result = await decideCloseReviewAction(INITIAL, form({
      companyId: COMPANY, packetId: PACKET,
      idempotencyKey: 'cls005-safe-command-04',
      decision: 'changes_requested', reasonCode: 'lineage_gap',
    }));
    expect(mocks.decide).toHaveBeenCalledWith(
      'synthetic-token', COMPANY, PACKET, 'cls005-safe-command-04', {
        decision: 'changes_requested', reason_code: 'lineage_gap',
      });
    expect(result.done).toMatch(/solicitud de cambios/i);
    expect(result.done).not.toMatch(/cerrado|certificado/i);
  });

  it('explica drift sin exponer el detalle de la API', async () => {
    mocks.decide.mockRejectedValue(new ApiError(
      409, 'internal source detail', 'close-review-evidence-stale'));
    const result = await decideCloseReviewAction(INITIAL, form({
      companyId: COMPANY, packetId: PACKET,
      idempotencyKey: 'cls005-safe-command-05',
      decision: 'changes_requested', reasonCode: 'quality_blocker',
    }));
    expect(result.error).toMatch(/evidencia cambio/i);
    expect(result.error).not.toContain('internal source detail');
    expect(mocks.revalidatePath).not.toHaveBeenCalled();
  });
});

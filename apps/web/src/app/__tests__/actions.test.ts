import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => {
  class ApiError extends Error {
    readonly status: number;

    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  }
  return {
    ApiError,
    createMapping: vi.fn(),
    fetchSource: vi.fn(),
    readSession: vi.fn(),
    redirect: vi.fn((): never => {
      throw new Error('NEXT_REDIRECT');
    }),
    revalidatePath: vi.fn(),
  };
});

vi.mock('next/cache', () => ({ revalidatePath: mocks.revalidatePath }));
vi.mock('next/navigation', () => ({ redirect: mocks.redirect }));
vi.mock('@/lib/session', () => ({
  clearSession: vi.fn(),
  readSession: mocks.readSession,
  writeSession: vi.fn(),
}));
vi.mock('@/lib/api', () => ({
  ApiError: mocks.ApiError,
  continueDataset: vi.fn(),
  createAccount: vi.fn(),
  createMapping: mocks.createMapping,
  createSource: vi.fn(),
  decideAmbiguity: vi.fn(),
  fetchSource: mocks.fetchSource,
  generateExpectations: vi.fn(),
  linkAccount: vi.fn(),
  prepareDataset: vi.fn(),
  publishDataset: vi.fn(),
  setCycle: vi.fn(),
  signIn: vi.fn(),
  updateAccount: vi.fn(),
  validateMapping: vi.fn(),
}));

import { createMappingAction } from '../actions';

function mappingForm(): FormData {
  const form = new FormData();
  form.set('companyId', '5f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5e');
  form.set('artifactId', '6f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5f');
  form.set('dataSourceId', '7f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d60');
  form.set('col_occurred_on', '0');
  form.set('col_description', '1');
  return form;
}

describe('createMappingAction', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.readSession.mockResolvedValue({
      token: 'token-sintetico',
      displayName: 'Ada',
    });
  });

  it('revalida la fuente y no crea el mapeo si fue retirada tras renderizar', async () => {
    mocks.fetchSource.mockResolvedValue({ status: 'inactive' });

    const result = await createMappingAction(
      { error: null, mappingVersionId: null, blockers: [] },
      mappingForm(),
    );

    expect(result.error).toContain('retirada');
    expect(mocks.createMapping).not.toHaveBeenCalled();
  });

  it('no distingue fuente inexistente de una fuente ya no disponible', async () => {
    mocks.fetchSource.mockRejectedValue(new mocks.ApiError(404, 'not found'));

    const result = await createMappingAction(
      { error: null, mappingVersionId: null, blockers: [] },
      mappingForm(),
    );

    expect(result.error).toContain('ya no esta disponible');
    expect(mocks.createMapping).not.toHaveBeenCalled();
  });
});

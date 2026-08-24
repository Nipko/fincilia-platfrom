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
    fetchDataset: vi.fn(),
    fetchMapping: vi.fn(),
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
  fetchDataset: mocks.fetchDataset,
  continueDataset: vi.fn(),
  createAccount: vi.fn(),
  createMapping: mocks.createMapping,
  fetchMapping: mocks.fetchMapping,
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

import {
  createMappingAction,
  prepareDatasetAction,
  publishDatasetAction,
  continueDatasetAction,
} from '../actions';

function mappingForm(): FormData {
  const form = new FormData();
  form.set('companyId', '5f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5e');
  form.set('artifactId', '6f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5f');
  form.set('dataSourceId', '7f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d60');
  form.set('col_occurred_on', '0');
  form.set('col_description', '1');
  return form;
}

function prepareForm(): FormData {
  const form = new FormData();
  form.set('companyId', '5f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5e');
  form.set('artifactId', '6f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5f');
  form.set('mappingVersionId', '8f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d70');
  form.set('financialAccountId', 'af0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d71');
  return form;
}

function datasetForm(): FormData {
  const form = new FormData();
  form.set('companyId', '5f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5e');
  form.set('artifactId', '6f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5f');
  form.set('datasetVersionId', '9f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d80');
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

describe('prepareDatasetAction', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.readSession.mockResolvedValue({
      token: 'token-sintetico',
      displayName: 'Ada',
    });
  });

  it('rechaza preparar un mapeo que ya no pertenece al documento', async () => {
    mocks.fetchMapping.mockResolvedValue({
      artifact_id: 'otro-documento',
      mapping_version_id: '8f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d70',
    });

    const result = await prepareDatasetAction(
      { error: null, datasetVersionId: null, summary: null, rejections: [] },
      prepareForm(),
    );

    expect(result.error).toContain('ya no pertenece');
    expect(mocks.fetchMapping).toHaveBeenCalledOnce();
  });
});

describe('publishDatasetAction', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.readSession.mockResolvedValue({
      token: 'token-sintetico',
      displayName: 'Ada',
    });
  });

  it('rechaza publicar una version de dataset de otro documento', async () => {
    mocks.fetchDataset.mockResolvedValue({
      dataset_version_id: '9f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d80',
      artifact_id: 'otro-documento',
      can_publish: true,
      movement_count: 0,
      state: 'validated',
      rejected_count: 0,
      prepared_at: '',
      published_at: null,
      record_count: 0,
      completeness_state: '',
      lineage_state: '',
      processing_run_id: '',
      prepared_by: '',
      validated_by: null,
      published_by: null,
      rejected_reason: null,
      canonical_schema_version: 'v0',
      engine_release: 'v-test',
      manifest: null,
    });

    const result = await publishDatasetAction(
      { error: null, published: null },
      datasetForm(),
    );

    expect(result.error).toContain('ya no pertenece');
    expect(mocks.fetchDataset).toHaveBeenCalledOnce();
  });
});

describe('continueDatasetAction', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.readSession.mockResolvedValue({
      token: 'token-sintetico',
      displayName: 'Ada',
    });
  });

  it('rechaza continuar una version que pertenece a otro documento', async () => {
    mocks.fetchDataset.mockResolvedValue({
      dataset_version_id: '9f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d80',
      artifact_id: 'otro-documento',
      state: 'staging',
      movement_count: 0,
      complete: false,
    } as never);

    const result = await continueDatasetAction(
      { error: null, progress: null },
      datasetForm(),
    );

    expect(result.error).toContain('no pertenece a este documento');
    expect(mocks.fetchDataset).toHaveBeenCalledOnce();
  });
});

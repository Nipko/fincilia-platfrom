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
    approveOverride: vi.fn(),
    fetchDataset: vi.fn(),
    fetchMapping: vi.fn(),
    fetchOverrides: vi.fn(),
    createMapping: vi.fn(),
    fetchSource: vi.fn(),
    rejectDataset: vi.fn(),
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
  approveOverride: mocks.approveOverride,
  fetchDataset: mocks.fetchDataset,
  continueDataset: vi.fn(),
  createAccount: vi.fn(),
  createMapping: mocks.createMapping,
  fetchMapping: mocks.fetchMapping,
  fetchOverrides: mocks.fetchOverrides,
  createSource: vi.fn(),
  decideAmbiguity: vi.fn(),
  fetchSource: mocks.fetchSource,
  generateExpectations: vi.fn(),
  linkAccount: vi.fn(),
  prepareDataset: vi.fn(),
  publishDataset: vi.fn(),
  rejectDataset: mocks.rejectDataset,
  setCycle: vi.fn(),
  signIn: vi.fn(),
  updateAccount: vi.fn(),
  validateMapping: vi.fn(),
}));

import {
  approveOverrideAction,
  createMappingAction,
  prepareDatasetAction,
  publishDatasetAction,
  continueDatasetAction,
  rejectDatasetAction,
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

function overrideForm(): FormData {
  const form = datasetForm();
  form.set('overrideId', 'bf0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d82');
  return form;
}

function rejectionForm(reason = 'La evidencia sintetica no soporta este resultado.'): FormData {
  const form = datasetForm();
  form.set('reason', reason);
  return form;
}

function matchingDataset() {
  return {
    dataset_version_id: '9f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d80',
    artifact_id: '6f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5f',
    can_publish: true,
    publish_blockers: [],
    state: 'validated',
  };
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
      publish_blockers: [],
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

describe('approveOverrideAction', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.readSession.mockResolvedValue({ token: 'token-sintetico', displayName: 'Ada' });
  });

  it('no aprueba si el dataset ya no pertenece al documento visible', async () => {
    mocks.fetchDataset.mockResolvedValue({ ...matchingDataset(), artifact_id: 'otro-documento' });

    const result = await approveOverrideAction(
      { error: null, done: null },
      overrideForm(),
    );

    expect(result.error).toContain('ya no pertenece');
    expect(mocks.fetchOverrides).not.toHaveBeenCalled();
    expect(mocks.approveOverride).not.toHaveBeenCalled();
  });

  it('no confia en un overrideId oculto que no pertenece al dataset visible', async () => {
    mocks.fetchDataset.mockResolvedValue(matchingDataset());
    mocks.fetchOverrides.mockResolvedValue([
      { override_id: 'otra-excepcion', needs_approval: true, approved: false },
    ]);

    const result = await approveOverrideAction(
      { error: null, done: null },
      overrideForm(),
    );

    expect(result.error).toContain('ya no pertenece');
    expect(mocks.approveOverride).not.toHaveBeenCalled();
  });

  it('explica la segregacion de funciones cuando el autor intenta aprobar', async () => {
    mocks.fetchDataset.mockResolvedValue(matchingDataset());
    mocks.fetchOverrides.mockResolvedValue([
      { override_id: 'bf0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d82' },
    ]);
    mocks.approveOverride.mockRejectedValue(new mocks.ApiError(409, 'conflict'));

    const result = await approveOverrideAction(
      { error: null, done: null },
      overrideForm(),
    );

    expect(result.error).toContain('no puede aprobarla');
    expect(mocks.revalidatePath).not.toHaveBeenCalled();
  });

  it('distingue una excepcion que ya no es aprobable', async () => {
    mocks.fetchDataset.mockResolvedValue(matchingDataset());
    mocks.fetchOverrides.mockResolvedValue([
      { override_id: 'bf0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d82' },
    ]);
    mocks.approveOverride.mockRejectedValue(new mocks.ApiError(422, 'invalid'));

    const result = await approveOverrideAction(
      { error: null, done: null },
      overrideForm(),
    );

    expect(result.error).toContain('estado actual');
    expect(mocks.revalidatePath).not.toHaveBeenCalled();
  });

  it('aprueba y revalida el puesto del documento', async () => {
    mocks.fetchDataset.mockResolvedValue(matchingDataset());
    mocks.fetchOverrides.mockResolvedValue([
      { override_id: 'bf0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d82' },
    ]);
    mocks.approveOverride.mockResolvedValue({ approved_by: 'revisor' });

    const result = await approveOverrideAction(
      { error: null, done: null },
      overrideForm(),
    );

    expect(result.done).toContain('aprobada');
    expect(mocks.approveOverride).toHaveBeenCalledOnce();
    expect(mocks.revalidatePath).toHaveBeenCalledWith(
      '/empresas/5f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5e/documentos/6f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5f/mapeo',
    );
  });
});

describe('rejectDatasetAction', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.readSession.mockResolvedValue({ token: 'token-sintetico', displayName: 'Ada' });
  });

  it('exige un motivo acotado antes de llamar a la API', async () => {
    const empty = await rejectDatasetAction(
      { error: null, done: null },
      rejectionForm('   '),
    );
    const tooLong = await rejectDatasetAction(
      { error: null, done: null },
      rejectionForm('x'.repeat(201)),
    );

    expect(empty.error).toContain('Explica');
    expect(tooLong.error).toContain('200');
    expect(mocks.rejectDataset).not.toHaveBeenCalled();
  });

  it('no rechaza un dataset de otro documento', async () => {
    mocks.fetchDataset.mockResolvedValue({ ...matchingDataset(), artifact_id: 'otro-documento' });

    const result = await rejectDatasetAction(
      { error: null, done: null },
      rejectionForm(),
    );

    expect(result.error).toContain('ya no pertenece');
    expect(mocks.rejectDataset).not.toHaveBeenCalled();
  });

  it('distingue permiso insuficiente de un estado que ya no admite rechazo', async () => {
    mocks.fetchDataset.mockResolvedValue(matchingDataset());
    mocks.rejectDataset.mockRejectedValueOnce(new mocks.ApiError(403, 'forbidden'));

    const forbidden = await rejectDatasetAction(
      { error: null, done: null },
      rejectionForm(),
    );
    mocks.rejectDataset.mockRejectedValueOnce(new mocks.ApiError(422, 'invalid'));
    const invalid = await rejectDatasetAction(
      { error: null, done: null },
      rejectionForm(),
    );

    expect(forbidden.error).toContain('rol');
    expect(invalid.error).toContain('estado actual');
    expect(mocks.revalidatePath).not.toHaveBeenCalled();
  });

  it('rechaza con el motivo y revalida el puesto del documento', async () => {
    mocks.fetchDataset.mockResolvedValue(matchingDataset());
    mocks.rejectDataset.mockResolvedValue({ state: 'rejected' });

    const result = await rejectDatasetAction(
      { error: null, done: null },
      rejectionForm('Periodo sintetico incompleto.'),
    );

    expect(result.done).toContain('auditado');
    expect(mocks.rejectDataset).toHaveBeenCalledWith(
      'token-sintetico',
      '5f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5e',
      '9f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d80',
      'Periodo sintetico incompleto.',
    );
    expect(mocks.revalidatePath).toHaveBeenCalledOnce();
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

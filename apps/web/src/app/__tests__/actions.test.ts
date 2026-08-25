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
    fetchCorrectionTargets: vi.fn(),
    fetchCorrections: vi.fn(),
    fetchDataset: vi.fn(),
    fetchMapping: vi.fn(),
    fetchOverrides: vi.fn(),
    proposeCorrection: vi.fn(),
    proposeReconciliationReview: vi.fn(),
    decideReconciliationReview: vi.fn(),
    reviewCorrection: vi.fn(),
    createMapping: vi.fn(),
    fetchSource: vi.fn(),
    grantMemberRole: vi.fn(),
    rejectDataset: vi.fn(),
    readSession: vi.fn(),
    revokeMemberRole: vi.fn(),
    redirect: vi.fn((): never => {
      throw new Error('NEXT_REDIRECT');
    }),
    revalidatePath: vi.fn(),
    writeSession: vi.fn(),
  };
});

vi.mock('next/cache', () => ({ revalidatePath: mocks.revalidatePath }));
vi.mock('next/navigation', () => ({ redirect: mocks.redirect }));
vi.mock('@/lib/session', () => ({
  clearSession: vi.fn(),
  readSession: mocks.readSession,
  writeSession: mocks.writeSession,
}));
vi.mock('@/lib/api', () => ({
  ApiError: mocks.ApiError,
  approveOverride: mocks.approveOverride,
  fetchCorrectionTargets: mocks.fetchCorrectionTargets,
  fetchCorrections: mocks.fetchCorrections,
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
  grantMemberRole: mocks.grantMemberRole,
  linkAccount: vi.fn(),
  prepareDataset: vi.fn(),
  publishDataset: vi.fn(),
  proposeCorrection: mocks.proposeCorrection,
  proposeReconciliationReview: mocks.proposeReconciliationReview,
  decideReconciliationReview: mocks.decideReconciliationReview,
  rejectDataset: mocks.rejectDataset,
  reviewCorrection: mocks.reviewCorrection,
  revokeMemberRole: mocks.revokeMemberRole,
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
  proposeCorrectionAction,
  reviewCorrectionAction,
  continueDatasetAction,
  rejectDatasetAction,
  proposeMatchAction,
  decideMatchAction,
  grantMemberRoleAction,
  revokeMemberRoleAction,
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

function correctionForm(): FormData {
  const form = datasetForm();
  form.set('movementId', 'cf0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d83');
  form.set('field', 'amount');
  form.set('expectedBaseDigest', 'a'.repeat(64));
  form.set('newValue', '1200.50');
  form.set('reasonCode', 'source_correction');
  form.set('reasonComment', 'Valor contrastado con evidencia sintetica.');
  return form;
}

function matchProposalForm(): FormData {
  const form = new FormData();
  form.set('companyId', '5f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5e');
  form.set('leftDatasetId', '6f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5f');
  form.set('rightDatasetId', '7f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d60');
  form.set('leftMovementId', '8f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d70');
  form.set('rightMovementId', '9f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d80');
  form.set('maxDays', '3');
  form.set('idempotencyKey', 'rec002-propose-test-0001');
  return form;
}

function matchDecisionForm(): FormData {
  const form = new FormData();
  form.set('companyId', '5f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5e');
  form.set('candidateId', 'af0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d71');
  form.set('decision', 'confirmed');
  form.set('reasonCode', 'documented_counterpart');
  form.set('idempotencyKey', 'rec002-confirm-test-0001');
  return form;
}

function correctionReviewForm(): FormData {
  const form = datasetForm();
  form.set('overlayId', 'df0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d84');
  form.set('decision', 'approved');
  form.set('rationale', 'Revision independiente sintetica.');
  return form;
}

function roleForm(): FormData {
  const form = new FormData();
  form.set('companyId', '5f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5e');
  form.set('subjectId', '6f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5f');
  form.set('role', 'reviewer');
  form.set('reasonCode', 'access_required');
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

describe('typed correction actions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.readSession.mockResolvedValue({ token: 'token-sintetico', displayName: 'Ada' });
    mocks.fetchDataset.mockResolvedValue(matchingDataset());
    mocks.fetchCorrectionTargets.mockResolvedValue([
      {
        field: 'amount', value_type: 'money_decimal',
        current_value: '1000.000000000000', expected_base_digest: 'a'.repeat(64),
      },
    ]);
  });

  it('no confia en el digest oculto si la lectura autorizada ya cambio', async () => {
    const form = correctionForm();
    form.set('expectedBaseDigest', 'b'.repeat(64));

    const result = await proposeCorrectionAction(
      { error: null, done: null }, form,
    );

    expect(result.error).toContain('cambio');
    expect(mocks.proposeCorrection).not.toHaveBeenCalled();
  });

  it('propone sin afirmar que el movimiento quedo modificado', async () => {
    mocks.proposeCorrection.mockResolvedValue({ overlay_id: 'overlay-sintetico' });

    const result = await proposeCorrectionAction(
      { error: null, done: null }, correctionForm(),
    );

    expect(result.done).toContain('no cambia el movimiento');
    expect(mocks.proposeCorrection).toHaveBeenCalledOnce();
    expect(mocks.revalidatePath).toHaveBeenCalledTimes(2);
  });

  it('no revisa un overlay oculto que no esta en el dataset visible', async () => {
    mocks.fetchCorrections.mockResolvedValue([
      { overlay_id: 'otra-propuesta', status: 'pending_review' },
    ]);

    const result = await reviewCorrectionAction(
      { error: null, done: null }, correctionReviewForm(),
    );

    expect(result.error).toContain('ya no esta pendiente');
    expect(mocks.reviewCorrection).not.toHaveBeenCalled();
  });

  it('explica que aprobar deja pendiente la aplicacion en otra version', async () => {
    mocks.fetchCorrections.mockResolvedValue([
      {
        overlay_id: 'df0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d84',
        status: 'pending_review',
      },
    ]);
    mocks.reviewCorrection.mockResolvedValue({ decision: 'approved', applied: false });

    const result = await reviewCorrectionAction(
      { error: null, done: null }, correctionReviewForm(),
    );

    expect(result.done).toContain('pendiente de aplicar');
    expect(mocks.reviewCorrection).toHaveBeenCalledOnce();
  });
});

describe('reconciliation review actions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.readSession.mockResolvedValue({ token: 'token-sintetico', displayName: 'Ada' });
  });

  it('rechaza contexto manipulado antes de llamar a la API', async () => {
    const form = matchProposalForm();
    form.set('leftMovementId', 'movimiento-ajeno');

    const result = await proposeMatchAction({ error: null, done: null }, form);

    expect(result.error).toContain('contexto valido');
    expect(mocks.proposeReconciliationReview).not.toHaveBeenCalled();
  });

  it('explica que proponer no cambia movimientos ni saldos', async () => {
    mocks.proposeReconciliationReview.mockResolvedValue({
      created: true, replayed: false, financial_effect: 'none',
    });

    const result = await proposeMatchAction(
      { error: null, done: null }, matchProposalForm(),
    );

    expect(result.done).toContain('No cambia movimientos ni saldos');
    expect(mocks.proposeReconciliationReview).toHaveBeenCalledOnce();
    expect(mocks.revalidatePath).toHaveBeenCalledWith(
      '/empresas/5f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5e/conciliacion',
    );
  });

  it('no convierte un conflicto SoD en exito', async () => {
    mocks.decideReconciliationReview.mockRejectedValue(
      new mocks.ApiError(409, 'the proposer cannot confirm this candidate'),
    );

    const result = await decideMatchAction(
      { error: null, done: null }, matchDecisionForm(),
    );

    expect(result.error).toContain('segregacion de funciones');
    expect(result.done).toBeNull();
  });

  it('confirma solo como registro humano sin efecto financiero', async () => {
    mocks.decideReconciliationReview.mockResolvedValue({
      replayed: false, status: 'confirmed', financial_effect: 'none',
    });

    const result = await decideMatchAction(
      { error: null, done: null }, matchDecisionForm(),
    );

    expect(result.done).toContain('sin efecto sobre movimientos o saldos');
    expect(mocks.decideReconciliationReview).toHaveBeenCalledOnce();
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

describe('company member role actions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.readSession.mockResolvedValue({
      token: 'token-sintetico',
      displayName: 'Sofia',
    });
  });

  it('rechaza identificadores y roles fuera del contrato sin llamar a la API', async () => {
    const form = roleForm();
    form.set('subjectId', '../otra-persona');
    form.set('role', 'super_admin');

    const result = await grantMemberRoleAction(
      { error: null, done: null },
      form,
    );

    expect(result.error).toContain('contexto valido');
    expect(mocks.grantMemberRole).not.toHaveBeenCalled();
  });

  it('asigna el rol, reemplaza la sesion invalidada y revalida ambas vistas', async () => {
    mocks.grantMemberRole.mockResolvedValue({
      subject_id: '6f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5f',
      role: 'reviewer',
      changed: true,
      replayed: false,
      authorization_version: 8,
      refreshed_session: {
        token: 'token-renovado',
        expires_at: 2_000_000_000,
        display_name: 'Sofia Owner',
      },
    });

    const result = await grantMemberRoleAction(
      { error: null, done: null },
      roleForm(),
    );

    expect(result.done).toContain('Rol asignado');
    expect(mocks.grantMemberRole).toHaveBeenCalledWith(
      'token-sintetico',
      '5f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5e',
      '6f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5f',
      { role: 'reviewer', reason_code: 'access_required' },
    );
    expect(mocks.writeSession).toHaveBeenCalledWith(
      'token-renovado', 'Sofia Owner', 2_000_000_000,
    );
    expect(mocks.revalidatePath).toHaveBeenCalledWith(
      '/empresas/5f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5e/equipo',
    );
    expect(mocks.revalidatePath).toHaveBeenCalledWith(
      '/empresas/5f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5e',
    );
  });

  it('revoca con motivo de minimo privilegio y conserva el replay idempotente', async () => {
    const form = roleForm();
    form.set('reasonCode', 'least_privilege');
    mocks.revokeMemberRole.mockResolvedValue({
      subject_id: '6f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5f',
      role: 'reviewer',
      changed: false,
      replayed: true,
      authorization_version: 8,
      refreshed_session: null,
    });

    const result = await revokeMemberRoleAction(
      { error: null, done: null },
      form,
    );

    expect(result.done).toContain('ya estaba revocado');
    expect(mocks.revokeMemberRole).toHaveBeenCalledWith(
      'token-sintetico',
      expect.any(String),
      expect.any(String),
      { role: 'reviewer', reason_code: 'least_privilege' },
    );
    expect(mocks.writeSession).not.toHaveBeenCalled();
  });

  it('explica los conflictos de autopermiso y ultimo owner', async () => {
    mocks.revokeMemberRole.mockRejectedValue(new mocks.ApiError(409, 'last owner'));

    const result = await revokeMemberRoleAction(
      { error: null, done: null },
      roleForm(),
    );

    expect(result.error).toContain('ultimo owner');
    expect(result.done).toBeNull();
  });
});

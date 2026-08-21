/**
 * FNC-SEC-001 — Fixtures exclusivamente sintéticos.
 *
 * INVARIANTE: ningún identificador, nombre, NIT, correo, monto o documento de
 * este archivo corresponde a una persona o empresa real. Todos los sujetos
 * llevan el prefijo `subject_`, las empresas `company_`, las organizaciones
 * `firm_`/`org_` y los recursos el sufijo `_synthetic_*`, siguiendo
 * TENANCY_MODEL.md §9.1.
 */

/* ------------------------------- reloj --------------------------------- */

export const NOW = '2026-08-21T15:00:00.000Z';
export const T_PAST = '2026-01-01T00:00:00.000Z';
export const T_RECENT_PAST = '2026-08-01T00:00:00.000Z';
export const T_FUTURE = '2027-01-01T00:00:00.000Z';

/* --------------------------- identificadores --------------------------- */

export const ID = Object.freeze({
  companyC1: 'company_c1',
  companyC2: 'company_c2',

  firmAlpha: 'firm_alpha',
  firmBeta: 'firm_beta',
  orgSmeC1: 'org_sme_c1',

  subjectDirect: 'subject_direct',
  subjectAlphaPreparer: 'subject_alpha_preparer',
  subjectAlphaApprover: 'subject_alpha_approver',
  subjectBetaReviewer: 'subject_beta_reviewer',
  subjectOutsider: 'subject_outsider',

  spAlphaImportC1: 'sp_alpha_import_c1',
  spAlphaShared: 'sp_alpha_shared',

  engagementAlphaC1: 'engagement_alpha_c1',
  engagementBetaC1: 'engagement_beta_c1',
  engagementAlphaC2: 'engagement_alpha_c2',

  membershipDirectC1: 'company_membership_synthetic_direct_c1',
  membershipAlpha: 'org_membership_synthetic_alpha',
  membershipBeta: 'org_membership_synthetic_beta',

  movementC1: 'movement_synthetic_0001',
  movementC2: 'movement_synthetic_0002',
  closePeriodC1: 'close_period_synthetic_2026_07',
  portabilityPackageC1: 'portability_package_synthetic_0001',
  ruleC1: 'rule_synthetic_fee_tolerance',
});

export const VERSION_C1 = 7;
export const VERSION_C1_AFTER_REVOCATION = 8;
export const VERSION_C2 = 3;

/* ------------------------------ utilidades ----------------------------- */

const isPlainObject = (v) =>
  typeof v === 'object' && v !== null && !Array.isArray(v);

/** Merge profundo: los objetos se fusionan; arrays, null y escalares reemplazan. */
export function merge(base, patch) {
  if (!isPlainObject(patch)) return patch;
  const out = { ...base };
  for (const [key, value] of Object.entries(patch)) {
    out[key] = isPlainObject(value) && isPlainObject(base?.[key])
      ? merge(base[key], value)
      : value;
  }
  return out;
}

/* ------------------------------ plantillas ----------------------------- */

const session = (assurance = 'AAL2', observedAuthorizationVersion = VERSION_C1) => ({
  id: 'session_synthetic_0001',
  status: 'active',
  assurance,
  observedAuthorizationVersion,
});

const identity = (assurance = 'AAL2') => ({
  id: 'identity_synthetic_0001',
  status: 'active',
  assurance,
});

const EMPTY_SOD = Object.freeze({
  preparedBySubjectIds: [],
  ruleAuthorSubjectIds: [],
  reopenRequestedBySubjectIds: [],
  breakGlassActorSubjectIds: [],
  approverSubjectIds: [],
  availableIndependentApprovers: 2,
});

const CALM_SIGNALS = Object.freeze({
  deviceKnown: true,
  ipReputation: 'known',
  offHours: false,
  geoVelocityAnomaly: false,
});

const OPEN_POLICY = Object.freeze({
  minimumAssuranceOverride: null,
  singleOperator: null,
  breakGlass: null,
});

const NO_ASSETS = Object.freeze({ ownedAssetIds: [], licensedAssetIds: [] });

/**
 * Ruta directa de la PYME: `subject_direct` sobre `company_c1`.
 * Base de TST-TEN-001-P01.
 */
export function directRead(patch = {}) {
  return merge({
    now: NOW,
    request: {
      requestedCompanyId: ID.companyC1,
      resourceId: ID.movementC1,
      resourceKind: 'movement',
      action: 'financial.read',
      purpose: 'operate',
      phase: 'request',
    },
    resolved: {
      resourceCompanyId: ID.companyC1,
      resourceState: 'open',
      company: {
        companyId: ID.companyC1,
        status: 'active',
        authorizationVersion: VERSION_C1,
      },
      primaryOperatorEngagementId: ID.engagementAlphaC1,
    },
    principal: {
      kind: 'subject',
      id: ID.subjectDirect,
      status: 'active',
      identity: identity(),
      session: session(),
      credentialStatus: null,
      ownerKind: null,
      ownerId: null,
    },
    paths: {
      companyMembership: {
        id: ID.membershipDirectC1,
        subjectId: ID.subjectDirect,
        companyId: ID.companyC1,
        status: 'active',
        validFrom: T_PAST,
        validUntil: null,
      },
      organizationMembership: null,
      organizationStatus: null,
      engagement: null,
    },
    grant: {
      id: 'grant_synthetic_direct_read',
      principalKind: 'subject',
      principalId: ID.subjectDirect,
      companyId: ID.companyC1,
      resourceKinds: ['movement', 'close_period', 'evidence_document'],
      actions: ['financial.read', 'movement.list'],
      purposes: ['operate', 'review'],
      pathKind: 'direct',
      pathRef: ID.membershipDirectC1,
      status: 'active',
      validFrom: T_PAST,
      validUntil: null,
      minimumAssurance: 'AAL2',
      authorizationVersion: VERSION_C1,
    },
    sod: { ...EMPTY_SOD },
    signals: { ...CALM_SIGNALS },
    policy: { ...OPEN_POLICY },
    assets: { ...NO_ASSETS },
    responsibilities: [],
  }, patch);
}

/**
 * Ruta delegada: `subject_alpha_preparer` vía `firm_alpha` + `engagement_alpha_c1`.
 * Base de TST-TEN-001-P02.
 */
export function delegatedPrepare(patch = {}) {
  return merge(directRead({
    request: {
      resourceId: ID.closePeriodC1,
      resourceKind: 'close_period',
      action: 'close.prepare',
      purpose: 'operate',
    },
    resolved: { resourceState: 'open' },
    principal: { id: ID.subjectAlphaPreparer },
    paths: {
      companyMembership: null,
      organizationMembership: {
        id: ID.membershipAlpha,
        subjectId: ID.subjectAlphaPreparer,
        organizationId: ID.firmAlpha,
        status: 'active',
        roles: ['preparer'],
        validFrom: T_PAST,
        validUntil: null,
      },
      organizationStatus: 'active',
      engagement: {
        id: ID.engagementAlphaC1,
        organizationId: ID.firmAlpha,
        companyId: ID.companyC1,
        status: 'active',
        validFrom: T_PAST,
        validUntil: null,
        isPrimaryOperator: true,
      },
    },
    grant: {
      id: 'grant_synthetic_alpha_prepare',
      principalId: ID.subjectAlphaPreparer,
      resourceKinds: ['close_period', 'movement', 'adjustment'],
      actions: ['close.prepare', 'financial.read', 'financial.write'],
      purposes: ['operate'],
      pathKind: 'delegated',
      pathRef: ID.engagementAlphaC1,
    },
  }), patch);
}

/** Aprobador delegado de Alpha, sobre el mismo cierre. Assurance AAL3. */
export function delegatedApprove(patch = {}) {
  return merge(delegatedPrepare({
    request: { action: 'close.approve', purpose: 'review' },
    principal: {
      id: ID.subjectAlphaApprover,
      identity: identity('AAL3'),
      session: session('AAL3'),
    },
    paths: {
      organizationMembership: {
        subjectId: ID.subjectAlphaApprover,
        roles: ['close_approver'],
      },
    },
    grant: {
      id: 'grant_synthetic_alpha_approve',
      principalId: ID.subjectAlphaApprover,
      actions: ['close.approve'],
      purposes: ['review'],
      minimumAssurance: 'AAL3',
    },
    sod: { preparedBySubjectIds: [ID.subjectAlphaPreparer] },
  }), patch);
}

/** Beta asesor: engagement activo con grant de solo lectura. TST-TEN-001-P03. */
export function betaAdvisorRead(patch = {}) {
  return merge(delegatedPrepare({
    request: {
      resourceId: ID.movementC1,
      resourceKind: 'movement',
      action: 'financial.read',
      purpose: 'review',
    },
    principal: { id: ID.subjectBetaReviewer },
    paths: {
      organizationMembership: {
        id: ID.membershipBeta,
        subjectId: ID.subjectBetaReviewer,
        organizationId: ID.firmBeta,
        roles: ['reviewer'],
      },
      engagement: {
        id: ID.engagementBetaC1,
        organizationId: ID.firmBeta,
        companyId: ID.companyC1,
        status: 'active',
        validFrom: T_PAST,
        validUntil: null,
        isPrimaryOperator: false,
      },
    },
    grant: {
      id: 'grant_synthetic_beta_read',
      principalId: ID.subjectBetaReviewer,
      resourceKinds: ['movement'],
      actions: ['financial.read'],
      purposes: ['review'],
      pathKind: 'delegated',
      pathRef: ID.engagementBetaC1,
    },
  }), patch);
}

/** Engagement de Alpha congelado con grant contractual de portabilidad. P04. */
export function frozenPortabilityExport(patch = {}) {
  return merge(delegatedPrepare({
    request: {
      resourceId: ID.portabilityPackageC1,
      resourceKind: 'portability_package',
      action: 'portability.export',
      purpose: 'portability',
    },
    principal: {
      identity: identity('AAL3'),
      session: session('AAL3'),
    },
    paths: { engagement: { status: 'frozen' } },
    grant: {
      id: 'grant_synthetic_alpha_portability',
      resourceKinds: ['portability_package'],
      actions: ['portability.read', 'portability.export'],
      purposes: ['portability'],
      minimumAssurance: 'AAL3',
    },
  }), patch);
}

/** Service principal de importación de Alpha para C1. P05. */
export function servicePrincipalJob(patch = {}) {
  return merge(delegatedPrepare({
    request: {
      resourceId: ID.movementC1,
      resourceKind: 'movement',
      action: 'job.execute',
      purpose: 'operate',
      phase: 'pre_read',
    },
    principal: {
      kind: 'service_principal',
      id: ID.spAlphaImportC1,
      status: 'active',
      identity: null,
      session: null,
      credentialStatus: 'active',
      ownerKind: 'organization',
      ownerId: ID.firmAlpha,
    },
    paths: { organizationMembership: null, organizationStatus: null },
    grant: {
      id: 'grant_synthetic_sp_alpha_c1',
      principalKind: 'service_principal',
      principalId: ID.spAlphaImportC1,
      resourceKinds: ['movement'],
      actions: ['job.execute', 'job.publish'],
      purposes: ['operate'],
      pathKind: 'delegated',
      pathRef: ID.engagementAlphaC1,
      minimumAssurance: 'AAL1',
    },
  }), patch);
}

/** Tercero sin ninguna relación con C1. N16. */
export function outsiderRead(patch = {}) {
  return merge(directRead({
    principal: { id: ID.subjectOutsider },
    paths: { companyMembership: null, organizationMembership: null, engagement: null },
    grant: null,
  }), patch);
}

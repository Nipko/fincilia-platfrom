/**
 * FNC-SEC-001 — Catálogo cerrado de vocabulario y reason codes.
 *
 * Cada valor de dominio vive aquí. El kernel deniega cualquier término que no
 * aparezca en estos conjuntos: un vocabulario abierto convierte un typo en un
 * ALLOW silencioso.
 *
 * Spike descartable. No es autenticación productiva.
 */

const frozenSet = (...values) => Object.freeze(new Set(values));

/* ------------------------------------------------------------------ *
 * Estados (TENANCY_MODEL.md §4)
 * ------------------------------------------------------------------ */

export const SUBJECT_STATUS = frozenSet('active', 'suspended', 'deactivated');
export const IDENTITY_STATUS = frozenSet('pending', 'active', 'disabled', 'revoked');
export const SESSION_STATUS = frozenSet('active', 'revoked', 'expired');
export const ORGANIZATION_STATUS = frozenSet('active', 'suspended', 'closed');
export const MEMBERSHIP_STATUS = frozenSet('invited', 'active', 'suspended', 'revoked', 'expired');
export const COMPANY_STATUS = frozenSet('onboarding', 'active', 'suspended', 'closed');
export const ENGAGEMENT_STATUS = frozenSet(
  'draft', 'pending_acceptance', 'active', 'frozen', 'revoked', 'expired',
);
export const GRANT_STATUS = frozenSet('pending', 'active', 'suspended', 'revoked', 'expired');
export const SERVICE_PRINCIPAL_STATUS = frozenSet('active', 'suspended', 'revoked');
export const CREDENTIAL_STATUS = frozenSet('active', 'rotating', 'revoked');
export const RESOURCE_STATE = frozenSet(
  'draft', 'open', 'under_review', 'closed', 'reopened', 'archived',
);

/* ------------------------------------------------------------------ *
 * Acciones, finalidades y recursos
 * ------------------------------------------------------------------ */

export const ACTION = frozenSet(
  // lectura financiera
  'financial.read',
  'movement.list',
  'audit.read',
  // escritura financiera
  'financial.write',
  'adjustment.prepare',
  'adjustment.approve',
  // ciclo de cierre
  'close.prepare',
  'close.approve',
  'close.reopen.request',
  'close.reopen.approve',
  // reglas
  'rule.author',
  'rule.release.approve',
  // portabilidad
  'portability.read',
  'portability.export',
  // administración de la relación
  'engagement.transfer.initiate',
  'engagement.primary_operator.activate',
  'grant.issue',
  // no humano
  'job.execute',
  'job.publish',
  // excepcional
  'break_glass.execute',
  'break_glass.review',
  // administrativo puro
  'org.billing.manage',
  'org.member.manage',
);

export const PURPOSE = frozenSet(
  'operate',
  'review',
  'audit.read',
  'portability',
  'administration',
  'incident_response',
);

export const RESOURCE_KIND = frozenSet(
  'movement',
  'close_period',
  'adjustment',
  'rule',
  'evidence_document',
  'portability_package',
  'engagement',
  'grant',
  'audit_log',
  'org_settings',
);

export const PHASE = frozenSet('request', 'pre_read', 'pre_publish');
export const PATH_KIND = frozenSet('direct', 'delegated');
export const PRINCIPAL_KIND = frozenSet('subject', 'service_principal');
export const OWNER_KIND = frozenSet('organization', 'company');

/* ------------------------------------------------------------------ *
 * Clasificación de acciones
 * ------------------------------------------------------------------ */

/** Acciones que tocan datos o decisiones financieras de una company. */
export const FINANCIAL_ACTIONS = frozenSet(
  'financial.read', 'movement.list', 'financial.write',
  'adjustment.prepare', 'adjustment.approve',
  'close.prepare', 'close.approve', 'close.reopen.request', 'close.reopen.approve',
  'rule.author', 'rule.release.approve',
  'portability.read', 'portability.export',
  'job.execute', 'job.publish',
);

/** Acciones que mutan estado. Un engagement frozen o una company cerrada las niegan. */
export const MUTATING_ACTIONS = frozenSet(
  'financial.write', 'adjustment.prepare', 'adjustment.approve',
  'close.prepare', 'close.approve', 'close.reopen.request', 'close.reopen.approve',
  'rule.author', 'rule.release.approve',
  'grant.issue', 'job.execute', 'job.publish',
  'engagement.transfer.initiate', 'engagement.primary_operator.activate',
  'break_glass.execute',
);

/**
 * Único allowlist admitido bajo engagement `frozen`
 * (TENANCY_MODEL.md §6.1 y §8.3).
 */
export const FROZEN_ALLOWLIST = frozenSet('portability.read', 'portability.export');

/**
 * Acciones que solo puede recibir por vía delegada el engagement designado
 * `primary_accounting_operator` (TENANCY_MODEL.md §5.3.2).
 */
export const PRIMARY_OPERATOR_ONLY = frozenSet(
  'financial.write', 'close.prepare', 'close.approve', 'close.reopen.approve',
);

/** Acciones puramente administrativas: nunca conceden finanzas por sí solas. */
export const ADMINISTRATIVE_ACTIONS = frozenSet('org.billing.manage', 'org.member.manage');

/** Roles administrativos de organización. No implican acceso financiero (invariante §5.1.4). */
export const ADMINISTRATIVE_ROLES = frozenSet(
  'organization_owner', 'firm_admin', 'billing_admin', 'company_admin',
);

export const OPERATIONAL_ROLES = frozenSet(
  'preparer', 'reviewer', 'close_approver', 'auditor', 'viewer', 'client_collaborator',
);

export const ROLE = frozenSet(...ADMINISTRATIVE_ROLES, ...OPERATIONAL_ROLES);

/* ------------------------------------------------------------------ *
 * Assurance
 * ------------------------------------------------------------------ */

export const ASSURANCE = Object.freeze({ AAL1: 1, AAL2: 2, AAL3: 3 });
export const ASSURANCE_LEVEL = frozenSet('AAL1', 'AAL2', 'AAL3');

/** Assurance mínimo por acción cuando la política no fija uno más estricto. */
export const DEFAULT_MINIMUM_ASSURANCE = Object.freeze({
  'financial.read': 'AAL2',
  'movement.list': 'AAL2',
  'audit.read': 'AAL2',
  'financial.write': 'AAL2',
  'adjustment.prepare': 'AAL2',
  'adjustment.approve': 'AAL2',
  'close.prepare': 'AAL2',
  'close.approve': 'AAL3',
  'close.reopen.request': 'AAL2',
  'close.reopen.approve': 'AAL3',
  'rule.author': 'AAL2',
  'rule.release.approve': 'AAL3',
  'portability.read': 'AAL2',
  'portability.export': 'AAL3',
  'engagement.transfer.initiate': 'AAL3',
  'engagement.primary_operator.activate': 'AAL3',
  'grant.issue': 'AAL3',
  'job.execute': 'AAL1',
  'job.publish': 'AAL1',
  'break_glass.execute': 'AAL3',
  'break_glass.review': 'AAL3',
  'org.billing.manage': 'AAL2',
  'org.member.manage': 'AAL3',
});

/* ------------------------------------------------------------------ *
 * Reason codes estables
 * ------------------------------------------------------------------ */

export const RC = Object.freeze({
  // permitir
  ALLOW_DIRECT_PATH: 'ALLOW_DIRECT_PATH',
  ALLOW_DELEGATED_PATH: 'ALLOW_DELEGATED_PATH',
  ALLOW_SERVICE_PRINCIPAL: 'ALLOW_SERVICE_PRINCIPAL',
  ALLOW_PORTABILITY_SCOPE: 'ALLOW_PORTABILITY_SCOPE',

  // entrada
  DENY_MALFORMED_INPUT: 'DENY_MALFORMED_INPUT',
  DENY_UNKNOWN_FIELD: 'DENY_UNKNOWN_FIELD',
  DENY_UNKNOWN_ACTION: 'DENY_UNKNOWN_ACTION',
  DENY_UNKNOWN_PURPOSE: 'DENY_UNKNOWN_PURPOSE',
  DENY_UNKNOWN_RESOURCE_KIND: 'DENY_UNKNOWN_RESOURCE_KIND',
  DENY_UNKNOWN_STATE: 'DENY_UNKNOWN_STATE',
  DENY_UNKNOWN_PHASE: 'DENY_UNKNOWN_PHASE',
  DENY_UNSAFE_DEFAULT: 'DENY_UNSAFE_DEFAULT',

  // principal
  DENY_SUBJECT_NOT_ACTIVE: 'DENY_SUBJECT_NOT_ACTIVE',
  DENY_IDENTITY_NOT_ACTIVE: 'DENY_IDENTITY_NOT_ACTIVE',
  DENY_SESSION_NOT_ACTIVE: 'DENY_SESSION_NOT_ACTIVE',
  DENY_SUBJECT_MISMATCH_GRANT: 'DENY_SUBJECT_MISMATCH_GRANT',

  // assurance
  DENY_ASSURANCE_INSUFFICIENT: 'DENY_ASSURANCE_INSUFFICIENT',

  // resolución de empresa
  DENY_COMPANY_SCOPE_MISMATCH: 'DENY_COMPANY_SCOPE_MISMATCH',
  DENY_COMPANY_STATE_FORBIDS_ACTION: 'DENY_COMPANY_STATE_FORBIDS_ACTION',
  DENY_RESOURCE_NOT_RESOLVED: 'DENY_RESOURCE_NOT_RESOLVED',
  DENY_NOT_FOUND_UNIFORM: 'DENY_NOT_FOUND_UNIFORM',

  // ruta
  DENY_PATH_MISSING: 'DENY_PATH_MISSING',
  DENY_PATH_MEMBERSHIP_NOT_ACTIVE: 'DENY_PATH_MEMBERSHIP_NOT_ACTIVE',
  DENY_PATH_ENGAGEMENT_NOT_ACTIVE: 'DENY_PATH_ENGAGEMENT_NOT_ACTIVE',
  DENY_PATH_ENGAGEMENT_ORG_MISMATCH: 'DENY_PATH_ENGAGEMENT_ORG_MISMATCH',
  DENY_PATH_ENGAGEMENT_COMPANY_MISMATCH: 'DENY_PATH_ENGAGEMENT_COMPANY_MISMATCH',
  DENY_PATH_NOT_REFERENCED_BY_GRANT: 'DENY_PATH_NOT_REFERENCED_BY_GRANT',
  DENY_ENGAGEMENT_FROZEN_ACTION_NOT_ALLOWLISTED: 'DENY_ENGAGEMENT_FROZEN_ACTION_NOT_ALLOWLISTED',

  // grant
  DENY_NO_GRANT: 'DENY_NO_GRANT',
  DENY_GRANT_NOT_ACTIVE: 'DENY_GRANT_NOT_ACTIVE',
  DENY_GRANT_OUT_OF_VALIDITY: 'DENY_GRANT_OUT_OF_VALIDITY',
  DENY_GRANT_COMPANY_MISMATCH: 'DENY_GRANT_COMPANY_MISMATCH',
  DENY_GRANT_ACTION_MISMATCH: 'DENY_GRANT_ACTION_MISMATCH',
  DENY_GRANT_PURPOSE_MISMATCH: 'DENY_GRANT_PURPOSE_MISMATCH',
  DENY_GRANT_RESOURCE_MISMATCH: 'DENY_GRANT_RESOURCE_MISMATCH',
  DENY_AUTHORIZATION_VERSION_STALE: 'DENY_AUTHORIZATION_VERSION_STALE',

  // no confundir administración/propiedad con finanzas
  DENY_ADMIN_ROLE_NOT_FINANCIAL: 'DENY_ADMIN_ROLE_NOT_FINANCIAL',
  DENY_ASSET_OWNERSHIP_NOT_AUTHORIZATION: 'DENY_ASSET_OWNERSHIP_NOT_AUTHORIZATION',
  DENY_RESPONSIBILITY_NOT_AUTHORIZATION: 'DENY_RESPONSIBILITY_NOT_AUTHORIZATION',

  // operador primario
  DENY_PRIMARY_OPERATOR_CONFLICT: 'DENY_PRIMARY_OPERATOR_CONFLICT',
  DENY_NOT_PRIMARY_OPERATOR: 'DENY_NOT_PRIMARY_OPERATOR',

  // segregación de funciones
  DENY_SOD_SELF_APPROVAL: 'DENY_SOD_SELF_APPROVAL',
  DENY_SOD_RULE_AUTHOR_APPROVAL: 'DENY_SOD_RULE_AUTHOR_APPROVAL',
  DENY_SOD_REOPEN_SELF_APPROVAL: 'DENY_SOD_REOPEN_SELF_APPROVAL',
  DENY_SOD_BREAK_GLASS_SELF_REVIEW: 'DENY_SOD_BREAK_GLASS_SELF_REVIEW',
  DENY_SOD_SINGLE_OPERATOR_WITHOUT_POLICY: 'DENY_SOD_SINGLE_OPERATOR_WITHOUT_POLICY',

  // principal no humano
  DENY_SP_NOT_ACTIVE: 'DENY_SP_NOT_ACTIVE',
  DENY_SP_CREDENTIAL_NOT_ACTIVE: 'DENY_SP_CREDENTIAL_NOT_ACTIVE',
  DENY_SP_ROUTE_MISMATCH: 'DENY_SP_ROUTE_MISMATCH',
  DENY_SP_TARGET_COMPANY_MISMATCH: 'DENY_SP_TARGET_COMPANY_MISMATCH',

  // estado del recurso
  DENY_RESOURCE_STATE_FORBIDS_ACTION: 'DENY_RESOURCE_STATE_FORBIDS_ACTION',
});

/**
 * Obligaciones. Acompañan un ALLOW condicionado o explican qué haría falta
 * para levantar un DENY. Nunca sustituyen un grant.
 */
export const OBL = Object.freeze({
  STEP_UP_REQUIRED: 'OBL_STEP_UP_REQUIRED',
  REASON_REQUIRED: 'OBL_REASON_REQUIRED',
  POST_REVIEW_REQUIRED: 'OBL_POST_REVIEW_REQUIRED',
  SECOND_APPROVER_REQUIRED: 'OBL_SECOND_APPROVER_REQUIRED',
  AUDIT_HIGH_RISK_SIGNAL: 'OBL_AUDIT_HIGH_RISK_SIGNAL',
  REVALIDATE_BEFORE_READ: 'OBL_REVALIDATE_BEFORE_READ',
  REVALIDATE_BEFORE_PUBLISH: 'OBL_REVALIDATE_BEFORE_PUBLISH',
  PORTABILITY_SCOPE_ONLY: 'OBL_PORTABILITY_SCOPE_ONLY',
  BIND_RLS_COMPANY_CONTEXT: 'OBL_BIND_RLS_COMPANY_CONTEXT',
  AUDIT_DECISION: 'OBL_AUDIT_DECISION',
});

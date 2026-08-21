/**
 * FNC-SEC-001 — Validación estricta de entrada.
 *
 * Postura: allowlist total. Un campo desconocido, un enum desconocido o un
 * campo obligatorio ausente producen DENY, nunca una omisión tolerada.
 * Esto materializa «negar campos, estados, acciones o finalidades desconocidas».
 */

import {
  RC, ACTION, PURPOSE, RESOURCE_KIND, PHASE, PATH_KIND, PRINCIPAL_KIND, OWNER_KIND,
  IDENTITY_STATUS, SESSION_STATUS, MEMBERSHIP_STATUS, COMPANY_STATUS, ENGAGEMENT_STATUS,
  GRANT_STATUS, CREDENTIAL_STATUS, RESOURCE_STATE, ORGANIZATION_STATUS,
  ASSURANCE_LEVEL, ROLE,
} from './catalog.mjs';

const IP_REPUTATION = Object.freeze(new Set(['known', 'unknown', 'flagged']));
const ISO_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?Z$/;

/* ---------------------------- constructores ---------------------------- */

const str = (opts = {}) => ({ kind: 'string', ...opts });
const enumOf = (set, code) => ({ kind: 'string', enum: set, code });
const bool = () => ({ kind: 'boolean' });
const int = () => ({ kind: 'integer' });
const iso = (opts = {}) => ({ kind: 'iso', ...opts });
const arr = (items) => ({ kind: 'array', items });
const obj = (fields, opts = {}) => ({ kind: 'object', fields, ...opts });

/* ------------------------------- esquema ------------------------------- */

const SCHEMA = obj({
  now: iso(),

  request: obj({
    requestedCompanyId: str({ nullable: true }),
    resourceId: str({ nullable: true }),
    resourceKind: enumOf(RESOURCE_KIND, RC.DENY_UNKNOWN_RESOURCE_KIND),
    action: enumOf(ACTION, RC.DENY_UNKNOWN_ACTION),
    purpose: enumOf(PURPOSE, RC.DENY_UNKNOWN_PURPOSE),
    phase: enumOf(PHASE, RC.DENY_UNKNOWN_PHASE),
  }),

  resolved: obj({
    resourceCompanyId: str({ nullable: true }),
    resourceState: {
      kind: 'string', enum: RESOURCE_STATE, code: RC.DENY_UNKNOWN_STATE, nullable: true,
    },
    company: obj({
      companyId: str(),
      status: { kind: 'string', enum: COMPANY_STATUS, code: RC.DENY_UNKNOWN_STATE },
      authorizationVersion: int(),
    }, { nullable: true }),
    primaryOperatorEngagementId: str({ nullable: true }),
  }),

  principal: obj({
    kind: enumOf(PRINCIPAL_KIND, RC.DENY_MALFORMED_INPUT),
    id: str(),
    // El enum concreto depende de kind; se comprueba en el kernel.
    status: str(),
    identity: obj({
      id: str(),
      status: { kind: 'string', enum: IDENTITY_STATUS, code: RC.DENY_UNKNOWN_STATE },
      assurance: { kind: 'string', enum: ASSURANCE_LEVEL, code: RC.DENY_UNKNOWN_STATE },
    }, { nullable: true }),
    session: obj({
      id: str(),
      status: { kind: 'string', enum: SESSION_STATUS, code: RC.DENY_UNKNOWN_STATE },
      assurance: { kind: 'string', enum: ASSURANCE_LEVEL, code: RC.DENY_UNKNOWN_STATE },
      observedAuthorizationVersion: int(),
    }, { nullable: true }),
    credentialStatus: { kind: 'string', enum: CREDENTIAL_STATUS, code: RC.DENY_UNKNOWN_STATE, nullable: true },
    ownerKind: { kind: 'string', enum: OWNER_KIND, code: RC.DENY_MALFORMED_INPUT, nullable: true },
    ownerId: str({ nullable: true }),
  }),

  paths: obj({
    companyMembership: obj({
      id: str(),
      subjectId: str(),
      companyId: str(),
      status: { kind: 'string', enum: MEMBERSHIP_STATUS, code: RC.DENY_UNKNOWN_STATE },
      validFrom: iso(),
      validUntil: iso({ nullable: true }),
    }, { nullable: true }),
    organizationMembership: obj({
      id: str(),
      subjectId: str(),
      organizationId: str(),
      status: { kind: 'string', enum: MEMBERSHIP_STATUS, code: RC.DENY_UNKNOWN_STATE },
      roles: arr({ kind: 'string', enum: ROLE, code: RC.DENY_UNKNOWN_FIELD }),
      validFrom: iso(),
      validUntil: iso({ nullable: true }),
    }, { nullable: true }),
    organizationStatus: {
      kind: 'string', enum: ORGANIZATION_STATUS, code: RC.DENY_UNKNOWN_STATE, nullable: true,
    },
    engagement: obj({
      id: str(),
      organizationId: str(),
      companyId: str(),
      status: { kind: 'string', enum: ENGAGEMENT_STATUS, code: RC.DENY_UNKNOWN_STATE },
      validFrom: iso(),
      validUntil: iso({ nullable: true }),
      isPrimaryOperator: bool(),
    }, { nullable: true }),
  }),

  grant: obj({
    id: str(),
    principalKind: enumOf(PRINCIPAL_KIND, RC.DENY_MALFORMED_INPUT),
    principalId: str(),
    companyId: str(),
    resourceKinds: arr({ kind: 'string', enum: RESOURCE_KIND, code: RC.DENY_UNKNOWN_RESOURCE_KIND }),
    actions: arr({ kind: 'string', enum: ACTION, code: RC.DENY_UNKNOWN_ACTION }),
    purposes: arr({ kind: 'string', enum: PURPOSE, code: RC.DENY_UNKNOWN_PURPOSE }),
    pathKind: enumOf(PATH_KIND, RC.DENY_MALFORMED_INPUT),
    pathRef: str(),
    status: { kind: 'string', enum: GRANT_STATUS, code: RC.DENY_UNKNOWN_STATE },
    validFrom: iso(),
    validUntil: iso({ nullable: true }),
    minimumAssurance: { kind: 'string', enum: ASSURANCE_LEVEL, code: RC.DENY_UNKNOWN_STATE },
    authorizationVersion: int(),
  }, { nullable: true }),

  sod: obj({
    preparedBySubjectIds: arr(str()),
    ruleAuthorSubjectIds: arr(str()),
    reopenRequestedBySubjectIds: arr(str()),
    breakGlassActorSubjectIds: arr(str()),
    approverSubjectIds: arr(str()),
    availableIndependentApprovers: int(),
  }),

  signals: obj({
    deviceKnown: bool(),
    ipReputation: { kind: 'string', enum: IP_REPUTATION, code: RC.DENY_UNKNOWN_FIELD },
    offHours: bool(),
    geoVelocityAnomaly: bool(),
  }),

  policy: obj({
    minimumAssuranceOverride: {
      kind: 'string', enum: ASSURANCE_LEVEL, code: RC.DENY_UNKNOWN_STATE, nullable: true,
    },
    singleOperator: obj({
      policyId: str(),
      approved: bool(),
      reasonProvided: bool(),
    }, { nullable: true }),
    breakGlass: obj({
      ticketId: str(),
      approverSubjectId: str(),
    }, { nullable: true }),
  }),

  assets: obj({
    ownedAssetIds: arr(str()),
    licensedAssetIds: arr(str()),
  }),

  responsibilities: arr(str()),
});

/* ------------------------------ recorrido ------------------------------ */

const isPlainObject = (v) =>
  typeof v === 'object' && v !== null && !Array.isArray(v);

function walk(node, value, path, codes) {
  if (value === null) {
    if (node.nullable) return;
    codes.add(RC.DENY_MALFORMED_INPUT);
    return;
  }
  if (value === undefined) {
    codes.add(RC.DENY_MALFORMED_INPUT);
    return;
  }

  switch (node.kind) {
    case 'object': {
      if (!isPlainObject(value)) { codes.add(RC.DENY_MALFORMED_INPUT); return; }
      for (const key of Object.keys(value)) {
        if (!Object.hasOwn(node.fields, key)) { codes.add(RC.DENY_UNKNOWN_FIELD); return; }
      }
      for (const [key, child] of Object.entries(node.fields)) {
        if (!Object.hasOwn(value, key)) { codes.add(RC.DENY_MALFORMED_INPUT); continue; }
        walk(child, value[key], `${path}.${key}`, codes);
      }
      return;
    }
    case 'array': {
      if (!Array.isArray(value)) { codes.add(RC.DENY_MALFORMED_INPUT); return; }
      for (const [i, item] of value.entries()) walk(node.items, item, `${path}[${i}]`, codes);
      return;
    }
    case 'string': {
      if (typeof value !== 'string' || value.length === 0) {
        codes.add(RC.DENY_MALFORMED_INPUT);
        return;
      }
      if (node.enum && !node.enum.has(value)) codes.add(node.code ?? RC.DENY_UNKNOWN_FIELD);
      return;
    }
    case 'iso': {
      if (typeof value !== 'string' || !ISO_RE.test(value) || Number.isNaN(Date.parse(value))) {
        codes.add(RC.DENY_MALFORMED_INPUT);
      }
      return;
    }
    case 'boolean': {
      if (typeof value !== 'boolean') codes.add(RC.DENY_MALFORMED_INPUT);
      return;
    }
    case 'integer': {
      if (!Number.isSafeInteger(value)) codes.add(RC.DENY_MALFORMED_INPUT);
      return;
    }
    default:
      codes.add(RC.DENY_UNSAFE_DEFAULT);
  }
}

/**
 * @param {unknown} input
 * @returns {{ ok: boolean, codes: string[] }}
 */
export function validateInput(input) {
  const codes = new Set();
  walk(SCHEMA, input, '$', codes);
  return { ok: codes.size === 0, codes: [...codes].sort() };
}

/**
 * FNC-SEC-001 — Kernel de autorización puro y fail-closed.
 *
 * SPIKE DESCARTABLE. No autentica, no consulta bases de datos, no emite tokens
 * y no es una implementación productiva. Materializa las decisiones de
 * TENANCY_MODEL.md y RBAC_ABAC_SOD.md para poder probarlas.
 *
 * Contrato:
 *   authorize(input) -> { decision: "ALLOW"|"DENY", reasonCodes: string[], obligations: string[] }
 *
 * Garantías:
 *   - Nunca lanza. Cualquier fallo interno se convierte en DENY.
 *   - Pureza: el instante llega en `input.now`; no se consulta el reloj del sistema.
 *   - El resultado es inmutable.
 */

import { validateInput } from './validate.mjs';
import {
  RC, OBL, ASSURANCE, DEFAULT_MINIMUM_ASSURANCE,
  SUBJECT_STATUS, SERVICE_PRINCIPAL_STATUS,
  FINANCIAL_ACTIONS, MUTATING_ACTIONS, FROZEN_ALLOWLIST, PRIMARY_OPERATOR_ONLY,
  ADMINISTRATIVE_ROLES,
} from './catalog.mjs';

/* ------------------------------- helpers ------------------------------- */

const freezeResult = (decision, reasonCodes, obligations) => Object.freeze({
  decision,
  reasonCodes: Object.freeze([...new Set(reasonCodes)].sort()),
  obligations: Object.freeze([...new Set(obligations)].sort()),
});

const deny = (codes, obligations = []) => freezeResult('DENY', codes, obligations);
const allow = (codes, obligations) => freezeResult('ALLOW', codes, obligations);

/** Denegación uniforme: no revela existencia ni metadatos (TST-TEN-001-N16). */
const UNIFORM_DENY = freezeResult('DENY', [RC.DENY_NOT_FOUND_UNIFORM], []);

/** Intervalo semiabierto `valid_from <= now < valid_until` (TENANCY_MODEL.md §4). */
function withinValidity(record, nowMs) {
  const from = Date.parse(record.validFrom);
  if (!Number.isFinite(from) || nowMs < from) return false;
  if (record.validUntil === null) return true;
  const until = Date.parse(record.validUntil);
  if (!Number.isFinite(until)) return false;
  return nowMs < until;
}

const rank = (level) => ASSURANCE[level] ?? Number.POSITIVE_INFINITY;
const maxAssurance = (...levels) => {
  let best = 'AAL1';
  for (const level of levels) {
    if (level && rank(level) > rank(best)) best = level;
  }
  return best;
};

/* ------------------------------- kernel -------------------------------- */

/**
 * @param {unknown} input
 * @returns {{decision: 'ALLOW'|'DENY', reasonCodes: readonly string[], obligations: readonly string[]}}
 */
export function authorize(input) {
  try {
    const validation = validateInput(input);
    if (!validation.ok) return deny(validation.codes);
    return evaluate(input);
  } catch {
    // Un fallo interno jamás se convierte en ALLOW.
    return deny([RC.DENY_UNSAFE_DEFAULT]);
  }
}

function evaluate(i) {
  const nowMs = Date.parse(i.now);
  const { request, resolved, principal, paths, grant, sod, signals, policy, assets } = i;
  const { action, purpose, resourceKind, phase } = request;
  const isSubject = principal.kind === 'subject';
  const obligations = new Set([OBL.AUDIT_DECISION]);

  /* --- 1. Estado del principal ---------------------------------------- */
  const codes1 = [];
  if (isSubject) {
    if (!SUBJECT_STATUS.has(principal.status)) codes1.push(RC.DENY_UNKNOWN_STATE);
    else if (principal.status !== 'active') codes1.push(RC.DENY_SUBJECT_NOT_ACTIVE);
    if (principal.identity === null || principal.identity.status !== 'active') {
      codes1.push(RC.DENY_IDENTITY_NOT_ACTIVE);
    }
    if (principal.session === null || principal.session.status !== 'active') {
      codes1.push(RC.DENY_SESSION_NOT_ACTIVE);
    }
  } else {
    if (!SERVICE_PRINCIPAL_STATUS.has(principal.status)) codes1.push(RC.DENY_UNKNOWN_STATE);
    else if (principal.status !== 'active') codes1.push(RC.DENY_SP_NOT_ACTIVE);
    if (principal.credentialStatus !== 'active') codes1.push(RC.DENY_SP_CREDENTIAL_NOT_ACTIVE);
    if (principal.ownerKind === null || principal.ownerId === null) {
      codes1.push(RC.DENY_MALFORMED_INPUT);
    }
  }
  if (codes1.length > 0) return deny(codes1);

  /* --- 2. Resolución del recurso; nunca por el ID del cliente ---------- */
  if (resolved.company === null || resolved.resourceCompanyId === null) return UNIFORM_DENY;

  const companyId = resolved.company.companyId;
  if (resolved.resourceCompanyId !== companyId) {
    // Inconsistencia del resolutor server-side: fallar cerrado.
    return deny([RC.DENY_RESOURCE_NOT_RESOLVED]);
  }
  if (request.requestedCompanyId !== null && request.requestedCompanyId !== companyId) {
    // El cliente pidió una empresa distinta de la que realmente contiene el recurso.
    return deny([RC.DENY_COMPANY_SCOPE_MISMATCH]);
  }

  /* --- 3. ¿Existe una ruta establecida hacia esta company? ------------- */
  const directPath =
    paths.companyMembership !== null &&
    paths.companyMembership.companyId === companyId &&
    (!isSubject || paths.companyMembership.subjectId === principal.id);

  const delegatedPath =
    paths.organizationMembership !== null &&
    paths.engagement !== null &&
    paths.engagement.companyId === companyId &&
    paths.organizationMembership.organizationId === paths.engagement.organizationId &&
    (!isSubject || paths.organizationMembership.subjectId === principal.id);

  const spOwnedPath =
    !isSubject &&
    ((principal.ownerKind === 'company' && principal.ownerId === companyId) ||
      (principal.ownerKind === 'organization' &&
        paths.engagement !== null &&
        paths.engagement.organizationId === principal.ownerId &&
        paths.engagement.companyId === companyId));

  const hasEstablishedPath = directPath || delegatedPath || spOwnedPath;
  if (!hasEstablishedPath && grant === null) return UNIFORM_DENY;

  /* --- 4. Estado de la company ---------------------------------------- */
  const companyStatus = resolved.company.status;
  const mutating = MUTATING_ACTIONS.has(action);
  if ((companyStatus === 'suspended' || companyStatus === 'closed') && mutating) {
    return deny([RC.DENY_COMPANY_STATE_FORBIDS_ACTION]);
  }
  if (companyStatus === 'onboarding' &&
      (action === 'close.approve' || action === 'close.reopen.approve')) {
    return deny([RC.DENY_COMPANY_STATE_FORBIDS_ACTION]);
  }

  /* --- 5. Sin grant no hay permiso efectivo ---------------------------- */
  if (grant === null) {
    const codes = [RC.DENY_NO_GRANT];
    const adminRoles =
      paths.organizationMembership !== null &&
      paths.organizationMembership.roles.some((r) => ADMINISTRATIVE_ROLES.has(r));
    if (adminRoles && FINANCIAL_ACTIONS.has(action)) codes.push(RC.DENY_ADMIN_ROLE_NOT_FINANCIAL);
    if ((assets.ownedAssetIds.length > 0 || assets.licensedAssetIds.length > 0) &&
        FINANCIAL_ACTIONS.has(action)) {
      codes.push(RC.DENY_ASSET_OWNERSHIP_NOT_AUTHORIZATION);
    }
    if (i.responsibilities.length > 0 && FINANCIAL_ACTIONS.has(action)) {
      codes.push(RC.DENY_RESPONSIBILITY_NOT_AUTHORIZATION);
    }
    return deny(codes);
  }

  /* --- 6. El grant debe corresponder exactamente ----------------------- */
  const codes6 = [];
  if (grant.principalKind !== principal.kind || grant.principalId !== principal.id) {
    codes6.push(RC.DENY_SUBJECT_MISMATCH_GRANT);
  }
  if (grant.companyId !== companyId) {
    codes6.push(isSubject ? RC.DENY_GRANT_COMPANY_MISMATCH : RC.DENY_SP_TARGET_COMPANY_MISMATCH);
  }
  if (grant.status !== 'active') codes6.push(RC.DENY_GRANT_NOT_ACTIVE);
  if (!withinValidity(grant, nowMs)) codes6.push(RC.DENY_GRANT_OUT_OF_VALIDITY);
  if (!grant.actions.includes(action)) codes6.push(RC.DENY_GRANT_ACTION_MISMATCH);
  if (!grant.purposes.includes(purpose)) codes6.push(RC.DENY_GRANT_PURPOSE_MISMATCH);
  if (!grant.resourceKinds.includes(resourceKind)) codes6.push(RC.DENY_GRANT_RESOURCE_MISMATCH);
  if (codes6.length > 0) return deny(codes6);

  /* --- 7. La ruta referenciada por el grant debe estar vigente --------- */
  const codes7 = [];
  let pathReason = null;

  if (grant.pathKind === 'direct') {
    const cm = paths.companyMembership;
    if (cm === null || cm.id !== grant.pathRef) {
      codes7.push(RC.DENY_PATH_NOT_REFERENCED_BY_GRANT);
    } else {
      if (cm.companyId !== companyId) codes7.push(RC.DENY_PATH_ENGAGEMENT_COMPANY_MISMATCH);
      if (isSubject && cm.subjectId !== principal.id) codes7.push(RC.DENY_SUBJECT_MISMATCH_GRANT);
      if (cm.status !== 'active' || !withinValidity(cm, nowMs)) {
        codes7.push(RC.DENY_PATH_MEMBERSHIP_NOT_ACTIVE);
      }
    }
    pathReason = RC.ALLOW_DIRECT_PATH;
  } else {
    const eng = paths.engagement;
    const om = paths.organizationMembership;
    if (eng === null || eng.id !== grant.pathRef) {
      codes7.push(RC.DENY_PATH_NOT_REFERENCED_BY_GRANT);
    } else {
      if (eng.companyId !== companyId) codes7.push(RC.DENY_PATH_ENGAGEMENT_COMPANY_MISMATCH);

      if (eng.status === 'frozen') {
        if (!FROZEN_ALLOWLIST.has(action)) {
          codes7.push(RC.DENY_ENGAGEMENT_FROZEN_ACTION_NOT_ALLOWLISTED);
        } else {
          obligations.add(OBL.PORTABILITY_SCOPE_ONLY);
        }
      } else if (eng.status !== 'active') {
        codes7.push(RC.DENY_PATH_ENGAGEMENT_NOT_ACTIVE);
      }
      if (!withinValidity(eng, nowMs)) codes7.push(RC.DENY_PATH_ENGAGEMENT_NOT_ACTIVE);

      // Un service principal puede actuar por la organización sin membership humana.
      if (isSubject) {
        if (om === null) {
          codes7.push(RC.DENY_PATH_MISSING);
        } else {
          if (om.organizationId !== eng.organizationId) {
            codes7.push(RC.DENY_PATH_ENGAGEMENT_ORG_MISMATCH);
          }
          if (om.subjectId !== principal.id) codes7.push(RC.DENY_SUBJECT_MISMATCH_GRANT);
          if (om.status !== 'active' || !withinValidity(om, nowMs)) {
            codes7.push(RC.DENY_PATH_MEMBERSHIP_NOT_ACTIVE);
          }
        }
        if (paths.organizationStatus !== null && paths.organizationStatus !== 'active') {
          codes7.push(RC.DENY_PATH_MEMBERSHIP_NOT_ACTIVE);
        }
      }
    }
    pathReason = RC.ALLOW_DELEGATED_PATH;
  }
  if (codes7.length > 0) return deny(codes7, [...obligations]);

  /* --- 8. Ruta del service principal (TENANCY_MODEL.md §6.2) ----------- */
  if (!isSubject) {
    const routeOk =
      (principal.ownerKind === 'company' &&
        grant.pathKind === 'direct' &&
        principal.ownerId === companyId) ||
      (principal.ownerKind === 'organization' &&
        grant.pathKind === 'delegated' &&
        paths.engagement !== null &&
        paths.engagement.organizationId === principal.ownerId);
    if (!routeOk) return deny([RC.DENY_SP_ROUTE_MISMATCH], [...obligations]);
  }

  /* --- 9. authorization_version ---------------------------------------- */
  const currentVersion = resolved.company.authorizationVersion;
  const versionCodes = [];
  if (grant.authorizationVersion !== currentVersion) {
    versionCodes.push(RC.DENY_AUTHORIZATION_VERSION_STALE);
  }
  if (isSubject && principal.session.observedAuthorizationVersion !== currentVersion) {
    versionCodes.push(RC.DENY_AUTHORIZATION_VERSION_STALE);
  }
  if (versionCodes.length > 0) return deny(versionCodes, [...obligations]);

  /* --- 10. Operador contable primario (TENANCY_MODEL.md §5.3) ---------- */
  if (grant.pathKind === 'delegated' && PRIMARY_OPERATOR_ONLY.has(action)) {
    const eng = paths.engagement;
    if (!eng.isPrimaryOperator || resolved.primaryOperatorEngagementId !== eng.id) {
      return deny([RC.DENY_NOT_PRIMARY_OPERATOR], [...obligations]);
    }
  }
  if (action === 'engagement.primary_operator.activate') {
    const targetEngagementId = request.resourceId;
    if (resolved.primaryOperatorEngagementId !== null &&
        resolved.primaryOperatorEngagementId !== targetEngagementId) {
      return deny([RC.DENY_PRIMARY_OPERATOR_CONFLICT], [...obligations]);
    }
  }

  /* --- 11. Estado del recurso ------------------------------------------ */
  const reopenActions = action === 'close.reopen.request' || action === 'close.reopen.approve';
  if (resolved.resourceState === 'closed' && mutating && !reopenActions) {
    return deny([RC.DENY_RESOURCE_STATE_FORBIDS_ACTION], [...obligations]);
  }

  /* --- 12. Segregación de funciones ------------------------------------ */
  const codes12 = [];
  const actorId = principal.id;
  if ((action === 'close.approve' || action === 'adjustment.approve') &&
      sod.preparedBySubjectIds.includes(actorId)) {
    codes12.push(RC.DENY_SOD_SELF_APPROVAL);
  }
  if (action === 'rule.release.approve' && sod.ruleAuthorSubjectIds.includes(actorId)) {
    codes12.push(RC.DENY_SOD_RULE_AUTHOR_APPROVAL);
  }
  if (action === 'close.reopen.approve' && sod.reopenRequestedBySubjectIds.includes(actorId)) {
    codes12.push(RC.DENY_SOD_REOPEN_SELF_APPROVAL);
  }
  if (action === 'break_glass.review' && sod.breakGlassActorSubjectIds.includes(actorId)) {
    codes12.push(RC.DENY_SOD_BREAK_GLASS_SELF_REVIEW);
  }
  if (codes12.length > 0) return deny(codes12, [...obligations]);

  // Operación unipersonal: solo mediante política explícita, nunca por bypass.
  const APPROVAL_ACTIONS = new Set([
    'close.approve', 'adjustment.approve', 'rule.release.approve', 'close.reopen.approve',
  ]);
  let singleOperator = false;
  if (APPROVAL_ACTIONS.has(action) && sod.availableIndependentApprovers === 0) {
    const so = policy.singleOperator;
    if (so === null || so.approved !== true || so.reasonProvided !== true) {
      return deny([RC.DENY_SOD_SINGLE_OPERATOR_WITHOUT_POLICY], [
        ...obligations, OBL.SECOND_APPROVER_REQUIRED,
      ]);
    }
    singleOperator = true;
    obligations.add(OBL.REASON_REQUIRED);
    obligations.add(OBL.POST_REVIEW_REQUIRED);
    obligations.add(OBL.STEP_UP_REQUIRED);
  }

  /* --- 13. Señales: solo elevan exigencia, nunca identifican ni conceden */
  const riskySignal =
    signals.deviceKnown === false ||
    signals.ipReputation === 'flagged' ||
    signals.geoVelocityAnomaly === true;
  if (riskySignal || signals.offHours === true) obligations.add(OBL.AUDIT_HIGH_RISK_SIGNAL);

  /* --- 14. Assurance ---------------------------------------------------- */
  let required = maxAssurance(
    DEFAULT_MINIMUM_ASSURANCE[action],
    grant.minimumAssurance,
    policy.minimumAssuranceOverride,
  );
  if (riskySignal) required = maxAssurance(required, 'AAL3');
  if (singleOperator) required = maxAssurance(required, 'AAL3');

  const actual = isSubject ? principal.session.assurance : 'AAL1';
  if (rank(actual) < rank(required)) {
    return deny([RC.DENY_ASSURANCE_INSUFFICIENT], [...obligations, OBL.STEP_UP_REQUIRED]);
  }

  /* --- 15. Break-glass -------------------------------------------------- */
  if (action === 'break_glass.execute') {
    const bg = policy.breakGlass;
    if (bg === null || bg.approverSubjectId === actorId) {
      return deny([RC.DENY_SOD_BREAK_GLASS_SELF_REVIEW], [...obligations]);
    }
    obligations.add(OBL.REASON_REQUIRED);
    obligations.add(OBL.POST_REVIEW_REQUIRED);
  }

  /* --- 16. Revalidación de trabajo diferido ----------------------------- */
  if (phase === 'pre_read') obligations.add(OBL.REVALIDATE_BEFORE_PUBLISH);
  if (phase === 'pre_publish') obligations.add(OBL.REVALIDATE_BEFORE_READ);
  if (!isSubject) {
    obligations.add(OBL.REVALIDATE_BEFORE_READ);
    obligations.add(OBL.REVALIDATE_BEFORE_PUBLISH);
  }

  obligations.add(OBL.BIND_RLS_COMPANY_CONTEXT);

  const reasons = [isSubject ? pathReason : RC.ALLOW_SERVICE_PRINCIPAL];
  if (obligations.has(OBL.PORTABILITY_SCOPE_ONLY)) reasons.push(RC.ALLOW_PORTABILITY_SCOPE);
  return allow(reasons, [...obligations]);
}

/**
 * Recalcula un portafolio empresa por empresa (TENANCY_MODEL.md §5.2.7).
 * Nunca se sirve un conjunto consolidado desde caché.
 *
 * @param {unknown[]} inputs una entrada de autorización por company
 * @returns {string[]} companyIds autorizados, en orden estable
 */
export function resolvePortfolio(inputs) {
  if (!Array.isArray(inputs)) return [];
  const allowed = [];
  for (const input of inputs) {
    const outcome = authorize(input);
    if (outcome.decision !== 'ALLOW') continue;
    const companyId = input?.resolved?.company?.companyId;
    if (typeof companyId === 'string' && !allowed.includes(companyId)) allowed.push(companyId);
  }
  return allowed.sort();
}

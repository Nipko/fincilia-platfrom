/**
 * FNC-SEC-001 — Materialización de TST-TEN-001 (TENANCY_MODEL.md §9).
 * 7 casos positivos y 16 negativos, todos con datos sintéticos.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { authorize, resolvePortfolio } from '../src/authorize.mjs';
import { RC, OBL } from '../src/catalog.mjs';
import {
  ID, VERSION_C1, VERSION_C1_AFTER_REVOCATION, VERSION_C2,
  directRead, delegatedPrepare, betaAdvisorRead, frozenPortabilityExport,
  servicePrincipalJob, outsiderRead,
} from './fixtures.mjs';

const has = (result, code) => result.reasonCodes.includes(code);

/* ==================================================================== *
 * §9.2 Casos positivos
 * ==================================================================== */

test('TST-TEN-001-P01 · ruta directa activa lee un recurso de C1', () => {
  const out = authorize(directRead());
  assert.equal(out.decision, 'ALLOW');
  assert.ok(has(out, RC.ALLOW_DIRECT_PATH), 'la auditoría debe identificar la ruta directa');
  assert.ok(out.obligations.includes(OBL.BIND_RLS_COMPANY_CONTEXT));
});

test('TST-TEN-001-P02 · ruta delegada completa prepara una operación de C1', () => {
  const out = authorize(delegatedPrepare());
  assert.equal(out.decision, 'ALLOW');
  assert.ok(has(out, RC.ALLOW_DELEGATED_PATH));
});

test('TST-TEN-001-P03 · Alpha escribe y Beta lee; Beta no adquiere escritura', () => {
  const alphaWrite = authorize(delegatedPrepare({
    request: { action: 'financial.write', resourceKind: 'movement', resourceId: ID.movementC1 },
  }));
  assert.equal(alphaWrite.decision, 'ALLOW');

  const betaRead = authorize(betaAdvisorRead());
  assert.equal(betaRead.decision, 'ALLOW');

  const betaWrite = authorize(betaAdvisorRead({ request: { action: 'financial.write' } }));
  assert.equal(betaWrite.decision, 'DENY');
  assert.ok(has(betaWrite, RC.DENY_GRANT_ACTION_MISMATCH));
});

test('TST-TEN-001-P04 · engagement frozen exporta solo el alcance de portabilidad', () => {
  const out = authorize(frozenPortabilityExport());
  assert.equal(out.decision, 'ALLOW');
  assert.ok(has(out, RC.ALLOW_PORTABILITY_SCOPE));
  assert.ok(out.obligations.includes(OBL.PORTABILITY_SCOPE_ONLY));
});

test('TST-TEN-001-P05 · service principal ejecuta y publica en C1 tras revalidar', () => {
  const beforeRead = authorize(servicePrincipalJob({ request: { phase: 'pre_read' } }));
  assert.equal(beforeRead.decision, 'ALLOW');
  assert.ok(has(beforeRead, RC.ALLOW_SERVICE_PRINCIPAL));

  const beforePublish = authorize(servicePrincipalJob({
    request: { action: 'job.publish', phase: 'pre_publish' },
  }));
  assert.equal(beforePublish.decision, 'ALLOW');
  assert.ok(beforePublish.obligations.includes(OBL.REVALIDATE_BEFORE_PUBLISH));
});

test('TST-TEN-001-P06 · tras el cambio Alpha→Beta, Beta lee el histórico preexistente de C1', () => {
  const input = betaAdvisorRead({
    resolved: { company: { authorizationVersion: VERSION_C1_AFTER_REVOCATION } },
    grant: { authorizationVersion: VERSION_C1_AFTER_REVOCATION },
    principal: { session: { observedAuthorizationVersion: VERSION_C1_AFTER_REVOCATION } },
  });
  const out = authorize(input);
  assert.equal(out.decision, 'ALLOW');
  assert.equal(input.resolved.resourceCompanyId, ID.companyC1,
    'el histórico conserva company_c1; el cambio de firma no mueve registros');
});

test('TST-TEN-001-P07 · revocada Alpha, el subject directo accede con la nueva versión', () => {
  const out = authorize(directRead({
    resolved: { company: { authorizationVersion: VERSION_C1_AFTER_REVOCATION } },
    grant: { authorizationVersion: VERSION_C1_AFTER_REVOCATION },
    principal: { session: { observedAuthorizationVersion: VERSION_C1_AFTER_REVOCATION } },
  }));
  assert.equal(out.decision, 'ALLOW');
  assert.ok(has(out, RC.ALLOW_DIRECT_PATH));
});

/* ==================================================================== *
 * §9.3 Casos negativos y cross-tenant
 * ==================================================================== */

test('TST-TEN-001-N01 · engagement activo sin grant no concede acceso', () => {
  const out = authorize(delegatedPrepare({ grant: null }));
  assert.equal(out.decision, 'DENY');
  assert.ok(has(out, RC.DENY_NO_GRANT));
});

test('TST-TEN-001-N02 · Organization Owner sin grant financiero no lista movimientos', () => {
  const out = authorize(delegatedPrepare({
    request: { action: 'movement.list', resourceKind: 'movement', resourceId: ID.movementC1 },
    paths: { organizationMembership: { roles: ['organization_owner', 'firm_admin'] } },
    grant: null,
  }));
  assert.equal(out.decision, 'DENY');
  assert.ok(has(out, RC.DENY_ADMIN_ROLE_NOT_FINANCIAL));
  assert.ok(has(out, RC.DENY_NO_GRANT));
});

test('TST-TEN-001-N03 · grant vivo sobre engagement revocado deniega', () => {
  const out = authorize(delegatedPrepare({ paths: { engagement: { status: 'revoked' } } }));
  assert.equal(out.decision, 'DENY');
  assert.ok(has(out, RC.DENY_PATH_ENGAGEMENT_NOT_ACTIVE));
});

test('TST-TEN-001-N04 · el company_id del cliente nunca autoriza', () => {
  // (a) El cliente declara C2 mientras el servidor resuelve C1 desde el recurso.
  const confusedDeputy = authorize(directRead({
    request: { requestedCompanyId: ID.companyC2 },
  }));
  assert.equal(confusedDeputy.decision, 'DENY');
  assert.ok(has(confusedDeputy, RC.DENY_COMPANY_SCOPE_MISMATCH));

  // (b) El recurso realmente vive en C2 y el grant es de C1.
  const honestRequestWrongGrant = authorize(directRead({
    request: { requestedCompanyId: ID.companyC2, resourceId: ID.movementC2 },
    resolved: {
      resourceCompanyId: ID.companyC2,
      company: { companyId: ID.companyC2, authorizationVersion: VERSION_C2 },
    },
  }));
  assert.equal(honestRequestWrongGrant.decision, 'DENY');
  assert.ok(has(honestRequestWrongGrant, RC.DENY_GRANT_COMPANY_MISMATCH));
});

test('TST-TEN-001-N05 · organization membership suspendida rompe la ruta delegada', () => {
  const out = authorize(delegatedPrepare({
    paths: { organizationMembership: { status: 'suspended' } },
  }));
  assert.equal(out.decision, 'DENY');
  assert.ok(has(out, RC.DENY_PATH_MEMBERSHIP_NOT_ACTIVE));
});

test('TST-TEN-001-N06 · engagement frozen deniega mutación, job y emisión de grant', () => {
  for (const action of ['financial.write', 'close.prepare']) {
    const out = authorize(delegatedPrepare({
      request: { action, resourceKind: 'movement', resourceId: ID.movementC1 },
      paths: { engagement: { status: 'frozen' } },
    }));
    assert.equal(out.decision, 'DENY', `frozen debe denegar ${action}`);
    assert.ok(has(out, RC.DENY_ENGAGEMENT_FROZEN_ACTION_NOT_ALLOWLISTED));
  }
});

test('TST-TEN-001-N07 · link, job y cache previos fallan cerrados tras subir la versión', () => {
  const out = authorize(directRead({
    resolved: { company: { authorizationVersion: VERSION_C1_AFTER_REVOCATION } },
    // El grant y la sesión conservan la versión anterior, como un enlace ya emitido.
  }));
  assert.equal(out.decision, 'DENY');
  assert.ok(has(out, RC.DENY_AUTHORIZATION_VERSION_STALE));
});

test('TST-TEN-001-N08 · el worker no puede desviar la capability de C1 hacia C2', () => {
  const out = authorize(servicePrincipalJob({
    request: { requestedCompanyId: ID.companyC2, resourceId: ID.movementC2 },
    resolved: {
      resourceCompanyId: ID.companyC2,
      company: { companyId: ID.companyC2, authorizationVersion: VERSION_C2 },
    },
  }));
  assert.equal(out.decision, 'DENY');
  assert.ok(has(out, RC.DENY_SP_TARGET_COMPANY_MISMATCH));
});

test('TST-TEN-001-N09 · no se activa un segundo operador primario', () => {
  const out = authorize(directRead({
    request: {
      resourceId: ID.engagementBetaC1,
      resourceKind: 'engagement',
      action: 'engagement.primary_operator.activate',
      purpose: 'administration',
    },
    principal: { session: { assurance: 'AAL3' }, identity: { assurance: 'AAL3' } },
    resolved: { primaryOperatorEngagementId: ID.engagementAlphaC1 },
    grant: {
      resourceKinds: ['engagement'],
      actions: ['engagement.primary_operator.activate'],
      purposes: ['administration'],
      minimumAssurance: 'AAL3',
    },
  }));
  assert.equal(out.decision, 'DENY');
  assert.ok(has(out, RC.DENY_PRIMARY_OPERATOR_CONFLICT));
});

test('TST-TEN-001-N10 · ownership o licencia de activo no autoriza finanzas', () => {
  const out = authorize(betaAdvisorRead({
    grant: null,
    assets: { ownedAssetIds: [ID.ruleC1], licensedAssetIds: [ID.ruleC1] },
  }));
  assert.equal(out.decision, 'DENY');
  assert.ok(has(out, RC.DENY_ASSET_OWNERSHIP_NOT_AUTHORIZATION));
  assert.ok(has(out, RC.DENY_NO_GRANT));
});

test('TST-TEN-001-N11 · un grant de audit.read no sirve para aprobar un cierre', () => {
  const out = authorize(directRead({
    request: {
      resourceId: ID.closePeriodC1,
      resourceKind: 'close_period',
      action: 'close.approve',
      purpose: 'review',
    },
    grant: { actions: ['audit.read'], purposes: ['audit.read'] },
  }));
  assert.equal(out.decision, 'DENY');
  assert.ok(has(out, RC.DENY_GRANT_ACTION_MISMATCH));
  assert.ok(has(out, RC.DENY_GRANT_PURPOSE_MISMATCH));
});

test('TST-TEN-001-N12 · la autorización usa subject_id, nunca el correo compartido', () => {
  const out = authorize(directRead({ principal: { id: ID.subjectOutsider } }));
  assert.equal(out.decision, 'DENY');
  assert.ok(has(out, RC.DENY_SUBJECT_MISMATCH_GRANT));
});

test('TST-TEN-001-N13 · el portafolio consolidado se recalcula empresa por empresa', () => {
  const stillAuthorizedOnC1 = directRead();
  const lostAccessToC2 = directRead({
    request: { requestedCompanyId: ID.companyC2, resourceId: ID.movementC2 },
    resolved: {
      resourceCompanyId: ID.companyC2,
      company: { companyId: ID.companyC2, authorizationVersion: VERSION_C2 },
    },
    paths: { companyMembership: null },
    grant: null,
  });

  const portfolio = resolvePortfolio([stillAuthorizedOnC1, lostAccessToC2]);
  assert.deepEqual(portfolio, [ID.companyC1], 'C2 no puede sobrevivir en la caché consolidada');
});

test('TST-TEN-001-N14 · el job aborta antes de publicar si la versión cambió', () => {
  const out = authorize(servicePrincipalJob({
    request: { action: 'job.publish', phase: 'pre_publish' },
    resolved: { company: { authorizationVersion: VERSION_C1_AFTER_REVOCATION } },
  }));
  assert.equal(out.decision, 'DENY');
  assert.ok(has(out, RC.DENY_AUTHORIZATION_VERSION_STALE));
});

test('TST-TEN-001-N15 · engagement Beta activo sin grants no concede acceso', () => {
  const out = authorize(betaAdvisorRead({ grant: null }));
  assert.equal(out.decision, 'DENY');
  assert.ok(has(out, RC.DENY_NO_GRANT));
});

test('TST-TEN-001-N16 · el tercero recibe una denegación uniforme sin metadatos', () => {
  const out = authorize(outsiderRead());
  assert.deepEqual(
    { decision: out.decision, reasonCodes: [...out.reasonCodes], obligations: [...out.obligations] },
    { decision: 'DENY', reasonCodes: [RC.DENY_NOT_FOUND_UNIFORM], obligations: [] },
    'no debe revelar existencia, empresa, ruta ni ausencia de grant',
  );

  // Indistinguible de un recurso inexistente.
  const nonExistent = authorize(outsiderRead({
    resolved: { resourceCompanyId: null, company: null },
  }));
  assert.deepEqual([...nonExistent.reasonCodes], [...out.reasonCodes]);
});

/* ==================================================================== *
 * §9.4 Aserciones de persistencia
 * ==================================================================== */

test('§9.4 · revocar el engagement no cambia company_id ni reescribe el recurso', () => {
  const before = delegatedPrepare();
  const after = delegatedPrepare({
    paths: { engagement: { status: 'revoked' } },
    resolved: { company: { authorizationVersion: VERSION_C1_AFTER_REVOCATION } },
  });

  assert.equal(before.resolved.resourceCompanyId, after.resolved.resourceCompanyId);
  assert.equal(after.resolved.resourceCompanyId, ID.companyC1);
  assert.equal(authorize(before).decision, 'ALLOW');
  assert.equal(authorize(after).decision, 'DENY');
  assert.notEqual(VERSION_C1, VERSION_C1_AFTER_REVOCATION);
});

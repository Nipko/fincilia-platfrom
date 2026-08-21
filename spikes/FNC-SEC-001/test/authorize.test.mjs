/**
 * FNC-SEC-001 — Semántica del kernel: fail-closed, assurance, SoD, señales,
 * pureza e inmutabilidad. Complementa tenancy.test.mjs.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { authorize } from '../src/authorize.mjs';
import { RC, OBL } from '../src/catalog.mjs';
import {
  ID, NOW,
  directRead, delegatedPrepare, delegatedApprove, betaAdvisorRead,
  servicePrincipalJob, outsiderRead,
} from './fixtures.mjs';

const has = (result, code) => result.reasonCodes.includes(code);

/* ==================================================================== *
 * Entrada desconocida o malformada
 * ==================================================================== */

test('deniega una acción desconocida', () => {
  const out = authorize(directRead({ request: { action: 'financial.delete' } }));
  assert.equal(out.decision, 'DENY');
  assert.ok(has(out, RC.DENY_UNKNOWN_ACTION));
});

test('deniega una finalidad desconocida', () => {
  const out = authorize(directRead({ request: { purpose: 'curiosity' } }));
  assert.equal(out.decision, 'DENY');
  assert.ok(has(out, RC.DENY_UNKNOWN_PURPOSE));
});

test('deniega un tipo de recurso desconocido', () => {
  const out = authorize(directRead({ request: { resourceKind: 'spreadsheet' } }));
  assert.equal(out.decision, 'DENY');
  assert.ok(has(out, RC.DENY_UNKNOWN_RESOURCE_KIND));
});

test('deniega un estado desconocido en cualquier registro de la ruta', () => {
  const cases = [
    directRead({ resolved: { company: { status: 'zombie' } } }),
    directRead({ grant: { status: 'almost_active' } }),
    delegatedPrepare({ paths: { engagement: { status: 'paused' } } }),
    directRead({ resolved: { resourceState: 'quantum' } }),
  ];
  for (const input of cases) {
    const out = authorize(input);
    assert.equal(out.decision, 'DENY');
    assert.ok(has(out, RC.DENY_UNKNOWN_STATE));
  }
});

test('deniega un campo desconocido en lugar de ignorarlo', () => {
  const input = directRead();
  input.request.impersonateSubjectId = ID.subjectDirect;
  const out = authorize(input);
  assert.equal(out.decision, 'DENY');
  assert.ok(has(out, RC.DENY_UNKNOWN_FIELD));
});

test('deniega cuando falta un bloque obligatorio', () => {
  const input = directRead();
  delete input.sod;
  const out = authorize(input);
  assert.equal(out.decision, 'DENY');
  assert.ok(has(out, RC.DENY_MALFORMED_INPUT));
});

/* ==================================================================== *
 * Nunca lanza; un fallo interno jamás se vuelve ALLOW
 * ==================================================================== */

test('nunca lanza: entradas basura producen DENY', () => {
  for (const junk of [undefined, null, 0, 'texto', [], true, Symbol('x'), () => {}, NaN]) {
    const out = authorize(junk);
    assert.equal(out.decision, 'DENY', `entrada ${String(junk)} debe denegar`);
  }
});

test('nunca lanza: un getter que explota produce DENY_UNSAFE_DEFAULT', () => {
  const bomb = {};
  Object.defineProperty(bomb, 'now', {
    enumerable: true,
    get() { throw new Error('fallo sintético de lectura'); },
  });
  const out = authorize(bomb);
  assert.equal(out.decision, 'DENY');
  assert.ok(has(out, RC.DENY_UNSAFE_DEFAULT));
});

test('nunca lanza: un Proxy hostil produce DENY', () => {
  const hostile = new Proxy({}, {
    ownKeys() { throw new Error('fallo sintético de enumeración'); },
  });
  const out = authorize(hostile);
  assert.equal(out.decision, 'DENY');
  assert.ok(has(out, RC.DENY_UNSAFE_DEFAULT));
});

test('una referencia circular no rompe el kernel', () => {
  const input = directRead();
  input.request.self = input;
  const out = authorize(input);
  assert.equal(out.decision, 'DENY');
});

/* ==================================================================== *
 * Pureza e inmutabilidad
 * ==================================================================== */

test('el resultado es inmutable y no se puede escalar a ALLOW', () => {
  const out = authorize(outsiderRead());
  assert.throws(() => { out.decision = 'ALLOW'; }, TypeError);
  assert.throws(() => { out.reasonCodes.push('ALLOW_DIRECT_PATH'); }, TypeError);
  assert.equal(out.decision, 'DENY');
});

test('es determinista y no muta la entrada', () => {
  const input = directRead();
  const snapshot = JSON.stringify(input);
  const first = authorize(input);
  const second = authorize(input);
  assert.equal(JSON.stringify(input), snapshot, 'la entrada no debe mutarse');
  assert.deepEqual(first, second);
});

test('no consulta el reloj del sistema: el instante llega en la entrada', () => {
  const expired = authorize(directRead({
    now: '2028-01-01T00:00:00.000Z',
    grant: { validUntil: '2027-01-01T00:00:00.000Z' },
  }));
  assert.equal(expired.decision, 'DENY');
  assert.ok(has(expired, RC.DENY_GRANT_OUT_OF_VALIDITY));
});

test('la vigencia es semiabierta: valid_until == now ya no autoriza', () => {
  const out = authorize(directRead({ grant: { validUntil: NOW } }));
  assert.equal(out.decision, 'DENY');
  assert.ok(has(out, RC.DENY_GRANT_OUT_OF_VALIDITY));
});

/* ==================================================================== *
 * Estado del principal
 * ==================================================================== */

test('subject suspendido, identidad revocada o sesión revocada deniegan', () => {
  const suspended = authorize(directRead({ principal: { status: 'suspended' } }));
  assert.ok(has(suspended, RC.DENY_SUBJECT_NOT_ACTIVE));

  const identityRevoked = authorize(directRead({ principal: { identity: { status: 'revoked' } } }));
  assert.ok(has(identityRevoked, RC.DENY_IDENTITY_NOT_ACTIVE));

  const sessionRevoked = authorize(directRead({ principal: { session: { status: 'revoked' } } }));
  assert.ok(has(sessionRevoked, RC.DENY_SESSION_NOT_ACTIVE));
});

/* ==================================================================== *
 * Assurance y step-up
 * ==================================================================== */

test('assurance insuficiente deniega y explica el step-up necesario', () => {
  const out = authorize(directRead({ principal: { session: { assurance: 'AAL1' } } }));
  assert.equal(out.decision, 'DENY');
  assert.ok(has(out, RC.DENY_ASSURANCE_INSUFFICIENT));
  assert.ok(out.obligations.includes(OBL.STEP_UP_REQUIRED));
});

test('la política del tenant puede exigir un assurance superior al de la acción', () => {
  const out = authorize(directRead({ policy: { minimumAssuranceOverride: 'AAL3' } }));
  assert.equal(out.decision, 'DENY');
  assert.ok(has(out, RC.DENY_ASSURANCE_INSUFFICIENT));
});

/* ==================================================================== *
 * Señales: nunca identidad, nunca grant
 * ==================================================================== */

test('un dispositivo desconocido eleva la exigencia, no concede ni identifica', () => {
  const denied = authorize(directRead({ signals: { deviceKnown: false } }));
  assert.equal(denied.decision, 'DENY');
  assert.ok(has(denied, RC.DENY_ASSURANCE_INSUFFICIENT));

  const allowed = authorize(directRead({
    signals: { deviceKnown: false },
    principal: { session: { assurance: 'AAL3' } },
  }));
  assert.equal(allowed.decision, 'ALLOW');
  assert.ok(allowed.obligations.includes(OBL.AUDIT_HIGH_RISK_SIGNAL));
});

test('una IP marcada o un salto geográfico se tratan como señal auditable', () => {
  const flagged = authorize(directRead({
    signals: { ipReputation: 'flagged' },
    principal: { session: { assurance: 'AAL3' } },
  }));
  assert.equal(flagged.decision, 'ALLOW');
  assert.ok(flagged.obligations.includes(OBL.AUDIT_HIGH_RISK_SIGNAL));

  const offHours = authorize(directRead({ signals: { offHours: true } }));
  assert.equal(offHours.decision, 'ALLOW', 'el horario por sí solo no deniega');
  assert.ok(offHours.obligations.includes(OBL.AUDIT_HIGH_RISK_SIGNAL));
});

test('señales perfectas no sustituyen un grant ni una ruta', () => {
  const out = authorize(outsiderRead({
    signals: { deviceKnown: true, ipReputation: 'known', offHours: false, geoVelocityAnomaly: false },
  }));
  assert.equal(out.decision, 'DENY');
});

/* ==================================================================== *
 * Segregación de funciones
 * ==================================================================== */

test('el aprobador independiente sí puede aprobar el cierre', () => {
  const out = authorize(delegatedApprove());
  assert.equal(out.decision, 'ALLOW');
});

test('el preparador no aprueba su propia preparación', () => {
  const out = authorize(delegatedApprove({
    sod: { preparedBySubjectIds: [ID.subjectAlphaApprover] },
  }));
  assert.equal(out.decision, 'DENY');
  assert.ok(has(out, RC.DENY_SOD_SELF_APPROVAL));
});

test('el autor de una regla no aprueba su propio release', () => {
  const out = authorize(delegatedApprove({
    request: { action: 'rule.release.approve', resourceKind: 'rule', resourceId: ID.ruleC1 },
    grant: { actions: ['rule.release.approve'], resourceKinds: ['rule'] },
    sod: { ruleAuthorSubjectIds: [ID.subjectAlphaApprover] },
  }));
  assert.equal(out.decision, 'DENY');
  assert.ok(has(out, RC.DENY_SOD_RULE_AUTHOR_APPROVAL));
});

test('quien solicita una reapertura no la aprueba', () => {
  const out = authorize(delegatedApprove({
    request: { action: 'close.reopen.approve' },
    resolved: { resourceState: 'closed' },
    grant: { actions: ['close.reopen.approve'] },
    sod: { reopenRequestedBySubjectIds: [ID.subjectAlphaApprover] },
  }));
  assert.equal(out.decision, 'DENY');
  assert.ok(has(out, RC.DENY_SOD_REOPEN_SELF_APPROVAL));
});

test('quien ejecuta un break-glass no revisa su propio acceso', () => {
  const out = authorize(directRead({
    request: { action: 'break_glass.review', resourceKind: 'audit_log', purpose: 'incident_response' },
    principal: { session: { assurance: 'AAL3' }, identity: { assurance: 'AAL3' } },
    grant: {
      actions: ['break_glass.review'],
      purposes: ['incident_response'],
      resourceKinds: ['audit_log'],
      minimumAssurance: 'AAL3',
    },
    sod: { breakGlassActorSubjectIds: [ID.subjectDirect] },
  }));
  assert.equal(out.decision, 'DENY');
  assert.ok(has(out, RC.DENY_SOD_BREAK_GLASS_SELF_REVIEW));
});

test('un break-glass sin aprobador registrado se deniega', () => {
  const out = authorize(directRead({
    request: { action: 'break_glass.execute', resourceKind: 'audit_log', purpose: 'incident_response' },
    principal: { session: { assurance: 'AAL3' }, identity: { assurance: 'AAL3' } },
    grant: {
      actions: ['break_glass.execute'],
      purposes: ['incident_response'],
      resourceKinds: ['audit_log'],
      minimumAssurance: 'AAL3',
    },
    policy: { breakGlass: null },
  }));
  assert.equal(out.decision, 'DENY');
});

/* ==================================================================== *
 * Operación unipersonal: política explícita, nunca bypass
 * ==================================================================== */

test('sin aprobador independiente y sin política, el cierre se deniega', () => {
  const out = authorize(delegatedApprove({
    sod: { availableIndependentApprovers: 0 },
  }));
  assert.equal(out.decision, 'DENY');
  assert.ok(has(out, RC.DENY_SOD_SINGLE_OPERATOR_WITHOUT_POLICY));
  assert.ok(out.obligations.includes(OBL.SECOND_APPROVER_REQUIRED));
});

test('una política unipersonal aprobada permite cerrar con obligaciones explícitas', () => {
  const out = authorize(delegatedApprove({
    sod: { availableIndependentApprovers: 0 },
    policy: {
      singleOperator: { policyId: 'policy_synthetic_single_operator', approved: true, reasonProvided: true },
    },
  }));
  assert.equal(out.decision, 'ALLOW');
  assert.ok(out.obligations.includes(OBL.REASON_REQUIRED));
  assert.ok(out.obligations.includes(OBL.POST_REVIEW_REQUIRED));
  assert.ok(out.obligations.includes(OBL.STEP_UP_REQUIRED));
});

test('una política unipersonal sin aprobar o sin motivo no basta', () => {
  for (const singleOperator of [
    { policyId: 'policy_synthetic_single_operator', approved: false, reasonProvided: true },
    { policyId: 'policy_synthetic_single_operator', approved: true, reasonProvided: false },
  ]) {
    const out = authorize(delegatedApprove({
      sod: { availableIndependentApprovers: 0 },
      policy: { singleOperator },
    }));
    assert.equal(out.decision, 'DENY');
    assert.ok(has(out, RC.DENY_SOD_SINGLE_OPERATOR_WITHOUT_POLICY));
  }
});

/* ==================================================================== *
 * Estados de company y de recurso
 * ==================================================================== */

test('una company suspendida o cerrada no admite mutaciones financieras', () => {
  for (const status of ['suspended', 'closed']) {
    const out = authorize(delegatedPrepare({ resolved: { company: { status } } }));
    assert.equal(out.decision, 'DENY');
    assert.ok(has(out, RC.DENY_COMPANY_STATE_FORBIDS_ACTION));
  }
});

test('un periodo cerrado rechaza escritura pero admite el flujo de reapertura', () => {
  const write = authorize(delegatedPrepare({
    request: { action: 'financial.write', resourceKind: 'movement', resourceId: ID.movementC1 },
    resolved: { resourceState: 'closed' },
  }));
  assert.equal(write.decision, 'DENY');
  assert.ok(has(write, RC.DENY_RESOURCE_STATE_FORBIDS_ACTION));

  const reopen = authorize(delegatedApprove({
    request: { action: 'close.reopen.approve' },
    resolved: { resourceState: 'closed' },
    grant: { actions: ['close.reopen.approve'] },
  }));
  assert.equal(reopen.decision, 'ALLOW');
});

/* ==================================================================== *
 * Operador contable primario
 * ==================================================================== */

test('un engagement delegado no primario no puede preparar ni cerrar', () => {
  const out = authorize(betaAdvisorRead({
    request: { action: 'close.prepare', resourceKind: 'close_period', resourceId: ID.closePeriodC1 },
    grant: { actions: ['close.prepare'], resourceKinds: ['close_period'], purposes: ['review'] },
  }));
  assert.equal(out.decision, 'DENY');
  assert.ok(has(out, RC.DENY_NOT_PRIMARY_OPERATOR));
});

/* ==================================================================== *
 * Principales no humanos
 * ==================================================================== */

test('un service principal revocado o con credencial revocada no opera', () => {
  const revoked = authorize(servicePrincipalJob({ principal: { status: 'revoked' } }));
  assert.ok(has(revoked, RC.DENY_SP_NOT_ACTIVE));

  const credential = authorize(servicePrincipalJob({ principal: { credentialStatus: 'revoked' } }));
  assert.ok(has(credential, RC.DENY_SP_CREDENTIAL_NOT_ACTIVE));
});

test('un service principal de company no puede usar la ruta delegada', () => {
  const out = authorize(servicePrincipalJob({
    principal: { ownerKind: 'company', ownerId: ID.companyC1 },
  }));
  assert.equal(out.decision, 'DENY');
  assert.ok(has(out, RC.DENY_SP_ROUTE_MISMATCH));
});

test('todo job obliga a revalidar antes de leer y antes de publicar', () => {
  const out = authorize(servicePrincipalJob());
  assert.equal(out.decision, 'ALLOW');
  assert.ok(out.obligations.includes(OBL.REVALIDATE_BEFORE_READ));
  assert.ok(out.obligations.includes(OBL.REVALIDATE_BEFORE_PUBLISH));
});

/* ==================================================================== *
 * Finalidad
 * ==================================================================== */

test('una finalidad válida pero no concedida deniega', () => {
  const out = authorize(directRead({ request: { purpose: 'audit.read' } }));
  assert.equal(out.decision, 'DENY');
  assert.ok(has(out, RC.DENY_GRANT_PURPOSE_MISMATCH));
});

test('todo ALLOW obliga a fijar el contexto de company para RLS', () => {
  for (const input of [directRead(), delegatedPrepare(), servicePrincipalJob()]) {
    const out = authorize(input);
    assert.equal(out.decision, 'ALLOW');
    assert.ok(out.obligations.includes(OBL.BIND_RLS_COMPANY_CONTEXT));
    assert.ok(out.obligations.includes(OBL.AUDIT_DECISION));
  }
});

import { randomUUID } from 'node:crypto';

import Link from 'next/link';
import { notFound, redirect } from 'next/navigation';

import { ReviewModeBadge } from '@/components/review-mode-badge';
import {
  ApiError,
  fetchCompany,
  fetchDatasets,
  fetchDocuments,
  fetchMe,
  fetchReconciliationRules,
  type ReconciliationRule,
} from '@/lib/api';
import { readSession } from '@/lib/session';
import {
  operatingProfileOf,
  PROFILE_LABELS,
  RULE_STATUS_LABELS,
  ruleActions,
  ruleApprovalLabel,
  selectSimplePair,
  type RuleAction,
  type SimplePair,
} from '@/lib/simple-mode';
import { ApplyRulesControl } from '../simple-inbox';
import { RuleControls } from './rule-controls';

export const dynamic = 'force-dynamic';

function Denied() {
  return (
    <main className="page-state page-state--denied">
      <p className="page-state__label">Acceso restringido</p>
      <h1>Reglas no disponibles</h1>
      <p className="page-state__description">
        Esta cuenta no tiene acceso vigente a las reglas de esta empresa.
      </p>
      <p className="page-state__action"><Link href="/empresas">Volver a empresas</Link></p>
    </main>
  );
}

function key(): string {
  return `smb-rule-${randomUUID()}`;
}

export default async function RulesPage({
  params,
}: {
  params: Promise<{ companyId: string }>;
}) {
  const session = await readSession();
  if (!session) redirect('/entrar');
  const { companyId } = await params;

  let company;
  try {
    company = await fetchCompany(session.token, companyId);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    if (error instanceof ApiError && error.status === 404) notFound();
    if (error instanceof ApiError && error.status === 403) return <Denied />;
    throw error;
  }
  if (!company.permissions.includes('movement.read')) return <Denied />;

  let rules: ReconciliationRule[] | null = null;
  let actorId = '';
  let pair: SimplePair | null = null;
  try {
    const [loaded, me, datasets, documents] = await Promise.all([
      fetchReconciliationRules(session.token, companyId),
      fetchMe(session.token),
      fetchDatasets(session.token, companyId),
      company.permissions.includes('document.read')
        ? fetchDocuments(session.token, companyId)
        : Promise.resolve([]),
    ]);
    rules = loaded;
    actorId = me.subject_id;
    pair = selectSimplePair(datasets, documents);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    if (error instanceof ApiError && error.status === 403) return <Denied />;
    rules = null;
  }

  const profile = operatingProfileOf(company);
  const encoded = encodeURIComponent(companyId);

  return (
    <main>
      <header className="bar">
        <div>
          <p className="meta">{company.legal_name}</p>
          <h1>Reglas de conciliación</h1>
        </div>
        <nav aria-label="Navegacion de reglas">
          <Link href={`/empresas/${encoded}`}>Volver a la empresa</Link>
        </nav>
      </header>

      <p className="lede">
        Una regla confirma sola un cruce que cumple todas sus condiciones, solo
        sobre archivos verificados y solo después de que una persona la aprueba.
        Perfil {PROFILE_LABELS[profile]}:{' '}
        {profile === 'simple'
          ? 'puedes aprobar tus propias reglas; quedan marcadas como autorrevisadas.'
          : 'otra persona aprueba cada regla.'}{' '}
        Pausar o retirar una regla no borra lo que ya confirmó, y cada
        aplicación se puede deshacer.
      </p>

      {pair && company.permissions.includes('match.propose') ? (
        <section className="card" aria-labelledby="apply-rules-heading">
          <h2 id="apply-rules-heading">Aplicar a los archivos publicados</h2>
          <p className="meta">
            Compara los dos archivos publicados más recientes de fuentes distintas.
          </p>
          <ApplyRulesControl companyId={companyId} pair={pair} applyKey={key()}
            revertKeyPrefix={key()} />
        </section>
      ) : null}

      {rules === null ? (
        <p className="notice" role="status">
          No se pudieron consultar las reglas en este momento.
        </p>
      ) : rules.length === 0 ? (
        <p className="card" role="status">
          Aún no hay reglas. Al confirmar un cruce en «Revisar pendientes» puedes
          elegir «¿Aplicar siempre?».
        </p>
      ) : (
        <ul className="pending-list" aria-label="Reglas de la empresa">
          {rules.map((rule) => {
            const actions = ruleActions(rule, {
              actorId, permissions: company.permissions, profile,
            });
            const keys = Object.fromEntries(
              (['approve', 'pause', 'resume', 'retire'] as RuleAction[])
                .map((action) => [action, key()]),
            ) as Record<RuleAction, string>;
            const approval = ruleApprovalLabel(rule);
            return (
              <li className="card pending-item" key={rule.rule_id}
                data-rule-status={rule.status}>
                <div className="tags">
                  <span className={`tag rule-status rule-status--${rule.status}`}>
                    {RULE_STATUS_LABELS[rule.status]}
                  </span>
                  {rule.approval ? <ReviewModeBadge mode={rule.approval.review_mode} /> : null}
                </div>
                <h3>Regla v{rule.version}</h3>
                <ul aria-label="Condiciones">
                  {rule.description.map((line, index) => (
                    <li key={`${rule.rule_id}:${index}`}>{line}</li>
                  ))}
                </ul>
                <p className="meta">
                  Creada por {rule.created_by_name}
                  {approval ? ` · ${approval}` : ' · pendiente de aprobación'}
                  {' · '}{rule.applied_count} aplicación(es), {rule.reverted_count} deshecha(s)
                </p>
                <RuleControls companyId={companyId} ruleId={rule.rule_id}
                  actions={actions} keys={keys} />
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}

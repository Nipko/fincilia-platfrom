import Link from 'next/link';
import { redirect } from 'next/navigation';

import {
  ApiError,
  fetchAccountsFull,
  fetchAssignees,
  fetchCompany,
  fetchExpectations,
  fetchLinks,
  fetchSourcesFull,
  type Account,
  type Assignee,
  type Expectation,
  type Source,
  type SourceCycle,
  type SourceLink,
} from '@/lib/api';
import { readSession } from '@/lib/session';

import {
  AccountForm,
  AccountStatusForm,
  CycleForm,
  LinkForm,
  SourceForm,
} from './onboarding-forms';

export const dynamic = 'force-dynamic';

const FAMILY_LABELS: Record<string, string> = {
  bank_account: 'cuenta bancaria',
  payment_gateway: 'pasarela de pagos',
  merchant_acquirer: 'adquirente',
  marketplace: 'marketplace',
  digital_wallet: 'billetera digital',
  billing_erp: 'ERP de facturacion',
  accounting_ledger: 'libro contable',
  tax_documents_received: 'documentos tributarios',
  supporting_evidence: 'soportes',
  reference_data: 'datos de referencia',
};

const ROLE_LABELS: Record<string, string> = {
  primary: 'principal',
  settlement: 'liquidacion',
  ledger: 'libro contable',
  supporting: 'soporte',
};

const STATUS_LABELS: Record<string, string> = {
  active: 'activa',
  suspended: 'suspendida',
  closed: 'cerrada',
};

export default async function SourcesPage({
  params,
}: {
  params: Promise<{ companyId: string }>;
}) {
  const session = await readSession();
  if (!session) {
    redirect('/entrar');
  }
  const { companyId } = await params;

  let company;
  try {
    company = await fetchCompany(session.token, companyId);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      redirect('/entrar');
    }
    return (
      <main>
        <header className="bar">
          <h1>Sin acceso</h1>
          <Link href="/empresas">Volver</Link>
        </header>
        <p className="card">Esta cuenta no tiene acceso vigente a lo que has pedido.</p>
      </main>
    );
  }

  const canManageAccounts = company.permissions.includes('financial_account.manage');
  const canManageSources = company.permissions.includes('data_source.manage');

  const [accounts, sources, links, expectations, people] = await Promise.all([
    fetchAccountsFull(session.token, companyId).catch(() => [] as Account[]),
    fetchSourcesFull(session.token, companyId).catch(() => [] as Source[]),
    fetchLinks(session.token, companyId).catch(() => [] as SourceLink[]),
    fetchExpectations(session.token, companyId).catch(() => [] as Expectation[]),
    // Quien puede responder de un ciclo sale de la base, no de quien mira la
    // pantalla: la version anterior ofrecia un solo candidato —tu— porque no
    // habia de donde sacar los demas.
    canManageSources
      ? fetchAssignees(session.token, companyId).catch(() => [] as Assignee[])
      : Promise.resolve([] as Assignee[]),
  ]);

  const linksBySource = new Map<string, SourceLink[]>();
  for (const link of links) {
    linksBySource.set(link.data_source_id,
                      [...(linksBySource.get(link.data_source_id) ?? []), link]);
  }
  const activeAccounts = accounts.filter((account) => account.status === 'active');
  // El ciclo vivo de cada fuente, para que el formulario sepa si su responsable
  // sigue valiendo. Se lee al abrir la fuente, no aqui, para no pedir uno por
  // fuente en cada carga de la pantalla.
  const cycleOf = new Map<string, SourceCycle>();
  const overdue = expectations.filter((item) => item.state === 'late');
  const today = new Date().toISOString().slice(0, 10);

  return (
    <main>
      <header className="bar">
        <div>
          <h1>Fuentes y cuentas</h1>
          <span className="who">{company.legal_name}</span>
        </div>
        <nav aria-label="Navegacion de la empresa">
          <Link href={`/empresas/${companyId}`}>Documentos</Link>{' '}
          <Link href="/empresas">Empresas</Link>
        </nav>
      </header>

      {accounts.length === 0 && sources.length === 0 ? (
        <p className="notice" role="status">
          Aqui todavia no hay nada. El orden es: crear una cuenta, crear una
          fuente, vincularlas, y entonces subir un documento. Sin cuenta y sin
          fuente no hay contra que publicar, y un movimiento siempre ocurre
          contra una cuenta.
        </p>
      ) : null}

      {overdue.length > 0 ? (
        <p className="notice error" role="status">
          Hay {overdue.length} periodo(s) atrasados. El mas antiguo lleva{' '}
          {Math.max(...overdue.map((item) => item.days_late))} dia(s) pasada la
          gracia.
        </p>
      ) : null}

      {/* ------------------------------------------------------- Cuentas --- */}
      <h2 id="cuentas">Cuentas</h2>
      {accounts.length === 0 ? (
        <p className="card">
          Sin cuentas. Un movimiento canonico siempre se registra contra una, asi
          que esto es lo primero.
        </p>
      ) : (
        <div className="card scroll">
          <table>
            <caption className="meta">
              El identificador no esta aqui ni en ningun sitio: lo que se guarda
              es una huella con clave y los cuatro ultimos digitos.
            </caption>
            <thead>
              <tr>
                <th scope="col">Cuenta</th>
                <th scope="col">Clase</th>
                <th scope="col">Moneda</th>
                <th scope="col">Cola</th>
                <th scope="col">Estado</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((account) => (
                <tr key={account.account_id}>
                  <th scope="row">{account.display_name}</th>
                  <td>{FAMILY_LABELS[account.account_family] ?? account.account_family}</td>
                  <td>{account.currency_code}</td>
                  <td className="when">
                    {account.identifier_last4 ? `...${account.identifier_last4}` : '—'}
                  </td>
                  <td>
                    <span className={`outcome ${account.status === 'active' ? '' : 'denied'}`}>
                      {STATUS_LABELS[account.status] ?? account.status}
                    </span>
                    {account.closed_reason ? (
                      <span className="meta"> · {account.closed_reason}</span>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {canManageAccounts ? (
        <section className="card" aria-labelledby="nueva-cuenta">
          <h3 id="nueva-cuenta">Crear una cuenta</h3>
          <AccountForm companyId={companyId} />
        </section>
      ) : (
        <p className="card">
          Administrar cuentas pide <code>financial_account.manage</code>. Dar de
          alta una cuenta decide contra que se publica todo lo que venga despues.
        </p>
      )}

      {canManageAccounts && accounts.length > 0 ? (
        <details className="card">
          <summary>Cambiar el estado de una cuenta</summary>
          {accounts.map((account) => (
            <section key={account.account_id}
                     aria-label={`Estado de ${account.display_name}`}>
              <div className="meta">
                <strong>{account.display_name}</strong> ·{' '}
                {STATUS_LABELS[account.status] ?? account.status}
                {account.usage
                  ? ` · ${account.usage.movements} movimiento(s)`
                  : ''}
              </div>
              <AccountStatusForm companyId={companyId} account={account} />
            </section>
          ))}
        </details>
      ) : null}

      {/* ------------------------------------------------------- Fuentes --- */}
      <h2 id="fuentes">Fuentes</h2>
      {sources.length === 0 ? (
        <p className="card">
          Sin fuentes. Una fuente es de donde viene la evidencia: un banco, una
          pasarela, un libro contable.
        </p>
      ) : (
        sources.map((source) => {
          const own = linksBySource.get(source.data_source_id) ?? [];
          const primary = own.find(
            (link) => link.relation_role === 'primary' && link.status === 'active');
          return (
            <section className="card" key={source.data_source_id}
                     aria-label={source.display_name}>
              <div className="meta">
                <strong>{source.display_name}</strong> ·{' '}
                {FAMILY_LABELS[source.source_family] ?? source.source_family} ·{' '}
                {source.purpose_code} ·{' '}
                <span className={`outcome ${source.status === 'active' ? '' : 'denied'}`}>
                  {STATUS_LABELS[source.status] ?? source.status}
                </span>
              </div>

              {own.length === 0 ? (
                <p className="notice error" role="status">
                  Esta fuente no tiene ninguna cuenta vinculada, asi que lo que
                  suba por ella no se puede publicar: no habria contra que.
                </p>
              ) : (
                <ul>
                  {own.map((link) => (
                    <li key={link.link_id}>
                      <strong>{ROLE_LABELS[link.relation_role] ?? link.relation_role}</strong>
                      {' · '}
                      {link.account_name}
                      {link.identifier_last4 ? ` ...${link.identifier_last4}` : ''}
                      {' · '}
                      <span className={`outcome ${link.status === 'active' ? '' : 'denied'}`}>
                        {STATUS_LABELS[link.status] ?? link.status}
                      </span>
                      {link.valid_to ? (
                        <span className="meta"> · hasta {link.valid_to}</span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}

              {!primary && own.length > 0 ? (
                <p className="notice" role="status">
                  Hay vinculos, pero ninguno principal. Publicar necesita saber
                  contra que cuenta, y esa es la que lo dice.
                </p>
              ) : null}

              {canManageSources ? (
                <>
                  <details>
                    <summary>Vincular una cuenta</summary>
                    <LinkForm companyId={companyId} source={source}
                              accounts={activeAccounts} />
                  </details>
                  <details>
                    <summary>Ciclo esperado</summary>
                    <CycleForm companyId={companyId} source={source}
                               people={people} cycle={cycleOf.get(source.data_source_id) ?? null}
                               today={today} />
                  </details>
                </>
              ) : null}

              {primary ? (
                <p className="meta">
                  <Link href={`/empresas/${companyId}`}>
                    Subir un documento para esta fuente
                  </Link>
                </p>
              ) : null}
            </section>
          );
        })
      )}

      {canManageSources ? (
        <section className="card" aria-labelledby="nueva-fuente">
          <h3 id="nueva-fuente">Crear una fuente</h3>
          <SourceForm companyId={companyId} />
        </section>
      ) : (
        <p className="card">
          Administrar fuentes pide <code>data_source.manage</code>.
        </p>
      )}

      {/* ------------------------------------------------------- Ciclos --- */}
      <h2 id="ciclos">Ciclos esperados</h2>
      {expectations.length === 0 ? (
        <p className="card">
          Ningun ciclo declarado todavia. Un cierre se retrasa por lo que no
          llego, y sin ciclo esa ausencia no tiene fecha contra la que medirse.
        </p>
      ) : (
        <div className="card scroll">
          <table>
            <caption className="meta">
              El atraso se calcula al leer, contra la fecha de hoy. Guardarlo
              exigiria un proceso nocturno, y el dia que no corriera nada
              estaria atrasado.
            </caption>
            <thead>
              <tr>
                <th scope="col">Fuente</th>
                <th scope="col">Periodo</th>
                <th scope="col">Vence</th>
                <th scope="col">Tarde desde</th>
                <th scope="col">Estado</th>
              </tr>
            </thead>
            <tbody>
              {expectations.map((item) => (
                <tr key={item.expectation_id}>
                  <th scope="row">{item.source_name}</th>
                  <td className="when">
                    {item.period_start} — {item.period_end}
                  </td>
                  <td className="when">{item.due_on}</td>
                  <td className="when">{item.late_after}</td>
                  <td>
                    <span className={`outcome ${item.state === 'late' ? 'denied' : ''}`}>
                      {item.state === 'late'
                        ? `atrasado ${item.days_late} dia(s)`
                        : item.state}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}

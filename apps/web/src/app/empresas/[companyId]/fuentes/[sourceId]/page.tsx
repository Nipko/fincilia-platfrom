import Link from 'next/link';
import { notFound, redirect } from 'next/navigation';

import {
  ApiError,
  fetchAccountsFull,
  fetchAssignees,
  fetchCompany,
  fetchSource,
  type Account,
  type Assignee,
} from '@/lib/api';
import { isoDateInTimeZone } from '@/lib/cycle-date';
import { withFlowContext } from '@/lib/navigation';
import { readSession } from '@/lib/session';

import { CycleForm, LinkForm } from '../onboarding-forms';

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

export default async function SourcePage({
  params,
}: {
  params: Promise<{ companyId: string; sourceId: string }>;
}) {
  const session = await readSession();
  if (!session) {
    redirect('/entrar');
  }
  const { companyId, sourceId } = await params;

  let company;
  let source;
  try {
    // SourceDetail ya incluye vinculos y ciclo. Esta es la unica lectura de la
    // fuente: pedir lista + detalle produciria dos verdades durante el render.
    [company, source] = await Promise.all([
      fetchCompany(session.token, companyId),
      fetchSource(session.token, companyId, sourceId),
    ]);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      redirect('/entrar');
    }
    if (error instanceof ApiError && error.status === 404) {
      notFound();
    }
    if (error instanceof ApiError && error.status === 403) {
      return (
        <main>
          <header className="bar">
            <h1>Sin acceso</h1>
            <Link href={`/empresas/${companyId}/fuentes`}>Volver</Link>
          </header>
          <p className="card">
            Esta cuenta no tiene acceso vigente a la fuente solicitada.
          </p>
        </main>
      );
    }
    throw error;
  }

  const canManage = company.permissions.includes('data_source.manage');
  let accounts: Account[] = [];
  let people: Assignee[] = [];
  if (canManage) {
    try {
      [accounts, people] = await Promise.all([
        fetchAccountsFull(session.token, companyId),
        fetchAssignees(session.token, companyId),
      ]);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        redirect('/entrar');
      }
      if (error instanceof ApiError && error.status === 403) {
        return (
          <main>
            <header className="bar">
              <h1>Sin acceso</h1>
              <Link href={`/empresas/${companyId}/fuentes`}>Volver</Link>
            </header>
            <p className="card">
              Esta cuenta ya no puede administrar la fuente solicitada.
            </p>
          </main>
        );
      }
      throw error;
    }
  }
  const activeAccounts = accounts.filter((account) => account.status === 'active');
  const primary = source.links.find(
    (link) => link.relation_role === 'primary' && link.status === 'active',
  );
  const today = isoDateInTimeZone(source.timezone);

  return (
    <main>
      <header className="bar">
        <div>
          <h1>{source.display_name}</h1>
          <span className="who">{company.legal_name}</span>
        </div>
        <nav aria-label="Navegacion de la fuente">
          <Link href={`/empresas/${companyId}/fuentes`}>Fuentes y cuentas</Link>{' '}
          <Link href={`/empresas/${companyId}`}>Documentos</Link>
        </nav>
      </header>

      <section className="card" aria-labelledby="resumen-fuente">
        <h2 id="resumen-fuente">Fuente</h2>
        <p className="meta">
          <strong>{FAMILY_LABELS[source.source_family] ?? source.source_family}</strong>
          {' · '}
          {source.purpose_code} · {source.timezone} ·{' '}
          <span className={`outcome ${source.status === 'active' ? '' : 'denied'}`}>
            {STATUS_LABELS[source.status] ?? source.status}
          </span>
        </p>
        {source.closed_reason ? <p>{source.closed_reason}</p> : null}
      </section>

      <h2 id="cuentas-vinculadas">Cuentas vinculadas</h2>
      {source.links.length === 0 ? (
        <p className="notice error" role="status">
          Esta fuente no tiene ninguna cuenta vinculada. Sin una cuenta
          principal activa no se puede publicar lo que venga de ella.
        </p>
      ) : (
        <div className="card scroll">
          <table>
            <caption className="meta">
              La cuenta principal responde contra que cuenta se publican los
              movimientos de esta fuente.
            </caption>
            <thead>
              <tr>
                <th scope="col">Papel</th>
                <th scope="col">Cuenta</th>
                <th scope="col">Moneda</th>
                <th scope="col">Estado</th>
              </tr>
            </thead>
            <tbody>
              {source.links.map((link) => (
                <tr key={link.link_id}>
                  <th scope="row">
                    {ROLE_LABELS[link.relation_role] ?? link.relation_role}
                  </th>
                  <td>
                    {link.account_name ?? 'Cuenta autorizada'}
                    {link.identifier_last4 ? ` · ...${link.identifier_last4}` : ''}
                  </td>
                  <td>{link.currency_code ?? '—'}</td>
                  <td>
                    <span className={`outcome ${link.status === 'active' ? '' : 'denied'}`}>
                      {STATUS_LABELS[link.status] ?? link.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!primary && source.links.length > 0 ? (
        <p className="notice" role="status">
          Hay vinculos, pero ninguno principal y activo. Publicar necesita una
          respuesta unica sobre la cuenta de destino.
        </p>
      ) : null}

      {canManage ? (
        <section className="card" aria-labelledby="vincular-cuenta">
          <h2 id="vincular-cuenta">Vincular una cuenta</h2>
          <LinkForm companyId={companyId} source={source} accounts={activeAccounts} />
        </section>
      ) : null}

      <h2 id="ciclo-esperado">Ciclo esperado</h2>
      {source.cycle ? (
        <p className="meta">
          Configuracion vigente: {source.cycle.periodicity} · plazo{' '}
          {source.cycle.due_day_offset} dia(s) · gracia {source.cycle.grace_days}{' '}
          dia(s) · desde {source.cycle.anchor_date} · {source.cycle.timezone}.
        </p>
      ) : (
        <p className="card">Esta fuente todavia no tiene un ciclo declarado.</p>
      )}
      {source.cycle?.responsible_eligible === false ? (
        <p className="notice error" role="alert">
          El responsable historico del ciclo ya no es elegible. El calendario se
          conserva, pero debe asignarse otra persona antes de guardarlo de nuevo.
        </p>
      ) : null}

      {canManage ? (
        <section className="card" aria-labelledby="editar-ciclo">
          <h3 id="editar-ciclo">
            {source.cycle ? 'Editar el ciclo' : 'Crear el ciclo'}
          </h3>
          <CycleForm
            companyId={companyId}
            source={source}
            people={people}
            cycle={source.cycle}
            today={today}
          />
        </section>
      ) : (
        <p className="card">
          Administrar el ciclo pide <code>data_source.manage</code>.
        </p>
      )}

      {primary ? (
        <p className="card">
          <Link
            href={withFlowContext(`/empresas/${companyId}`, {
              fuente: source.data_source_id,
            })}
          >
            Subir un documento para esta fuente
          </Link>
        </p>
      ) : null}
    </main>
  );
}

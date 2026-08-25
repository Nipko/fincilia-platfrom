import Link from 'next/link';
import { notFound, redirect } from 'next/navigation';

import {
  ApiError,
  fetchAccountBalances,
  fetchBalanceEvidence,
  fetchCompany,
  type AccountBalance,
  type BalanceEvidence,
} from '@/lib/api';
import { readSession } from '@/lib/session';

import { BalanceForm } from './balance-form';

export const dynamic = 'force-dynamic';

const TYPE_LABELS: Record<AccountBalance['balance_type'], string> = {
  opening: 'Inicial',
  closing: 'Final extracto',
  running: 'Acumulado',
  available: 'Disponible',
  ledger: 'Libros',
};

function exactMoney(value: string): string {
  return value.replace(/(\.\d*?[1-9])0+$|\.0+$/, '$1');
}

function formatInstant(value: string, timezone: string): string {
  return new Intl.DateTimeFormat('es-CO', {
    dateStyle: 'medium', timeStyle: 'short', timeZone: timezone,
  }).format(new Date(value));
}

export default async function BalancesPage({ params }: {
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
    if (error instanceof ApiError && error.status === 403) {
      return <main><h1>Sin acceso</h1><p className="card">La empresa ya no esta disponible.</p></main>;
    }
    throw error;
  }
  if (!company.permissions.includes('movement.read')) notFound();

  const canPrepare = company.permissions.includes('close.prepare');
  let balances: AccountBalance[] = [];
  let evidence: BalanceEvidence[] = [];
  let truncated = false;
  try {
    const [history, candidates] = await Promise.all([
      fetchAccountBalances(session.token, companyId, 100),
      canPrepare
        ? fetchBalanceEvidence(session.token, companyId, 20)
        : Promise.resolve({ limit: 20, truncated: false, items: [] }),
    ]);
    balances = history.items;
    evidence = candidates.items;
    truncated = history.truncated || candidates.truncated;
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    if (error instanceof ApiError && [403, 404].includes(error.status)) notFound();
    throw error;
  }

  return (
    <main>
      <header className="bar">
        <div>
          <h1>Saldos por cuenta</h1>
          <span className="who">{company.legal_name}</span>
        </div>
        <nav aria-label="Navegacion de saldos">
          <Link href={`/preparacion-cierre?empresa=${companyId}`}>Preparacion de cierre</Link>{' '}
          <Link href={`/empresas/${companyId}`}>Empresa</Link>
        </nav>
      </header>

      <p className="lede">
        Observaciones exactas tomadas de una celda publicada. Conservan cuenta,
        moneda, fecha y coordenada; no prueban por si solas completitud ni conciliacion.
      </p>
      <p className="notice close-readiness-warning" role="status">
        <strong>Estos saldos aun no son entrada de cierre.</strong>{' '}
        El camino completo de linaje del campo permanece pendiente y el estado de
        conciliacion todavia no esta materializado.
      </p>

      {canPrepare ? (
        <section className="card" aria-labelledby="observar-saldo">
          <h2 id="observar-saldo">Observar desde una fila publicada</h2>
          <BalanceForm companyId={companyId} evidence={evidence} />
        </section>
      ) : (
        <p className="card" role="status">
          Puedes consultar el historico. Preparar una observacion requiere el
          permiso <code>close.prepare</code>.
        </p>
      )}

      <section aria-labelledby="historico-saldos">
        <h2 id="historico-saldos">Historico inmutable</h2>
        {balances.length ? (
          <div className="card scroll">
            <table>
              <caption className="meta">
                {balances.length} observacion(es). Corregir exige otra evidencia;
                ninguna fila se edita ni se elimina.
              </caption>
              <thead><tr><th scope="col">Fecha</th><th scope="col">Cuenta</th>
                <th scope="col">Tipo</th><th scope="col">Saldo</th>
                <th scope="col">Evidencia</th><th scope="col">Linaje</th></tr></thead>
              <tbody>{balances.map((balance) => (
                <tr key={balance.balance_id}>
                  <td className="when">{formatInstant(balance.as_of, balance.source_timezone)}</td>
                  <th scope="row">{balance.account_name}</th>
                  <td>{TYPE_LABELS[balance.balance_type]}</td>
                  <td className="money-cell">
                    <strong>{exactMoney(balance.amount)}</strong> {balance.currency_code}
                  </td>
                  <td>{balance.source_name} · fila {balance.record_ordinal} · columnas{' '}
                    {balance.amount_field_index + 1}/{balance.as_of_field_index + 1}</td>
                  <td><span className={`outcome ${balance.lineage_state === 'complete' ? '' : 'denied'}`}>
                    {balance.lineage_state === 'complete' ? 'Completo' : 'Pendiente'}
                  </span></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : (
          <p className="card" role="status">
            Todavia no hay observaciones de saldo. Una lista vacia no significa saldo cero.
          </p>
        )}
      </section>

      {truncated ? (
        <p className="notice" role="status">
          Vista acotada: se muestran las filas mas recientes. Esto no se interpreta
          como historico completo.
        </p>
      ) : null}
    </main>
  );
}

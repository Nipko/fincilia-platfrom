import Link from 'next/link';
import { redirect } from 'next/navigation';

import { SignOut } from '@/app/empresas/sign-out';
import { ApiError, fetchMe } from '@/lib/api';
import {
  auditEntries,
  loadAuditCenter,
  parseAuditFilter,
} from '@/lib/audit-center';
import { readSession } from '@/lib/session';

export const dynamic = 'force-dynamic';

type Query = Record<string, string | string[] | undefined>;

const OUTCOME_LABEL: Record<string, string> = {
  allowed: 'Permitido', denied: 'Denegado', error: 'Error',
};

function when(value: string): string {
  return new Intl.DateTimeFormat('es-CO', {
    dateStyle: 'medium', timeStyle: 'short', timeZone: 'America/Bogota',
  }).format(new Date(value));
}

function nextHref(filter: ReturnType<typeof parseAuditFilter>, cursor: string) {
  const query = new URLSearchParams();
  if (filter.companyId) query.set('empresa', filter.companyId);
  if (filter.outcome !== 'all') query.set('resultado', filter.outcome);
  if (filter.action) query.set('accion', filter.action);
  if (filter.resourceKind) query.set('recurso', filter.resourceKind);
  query.set('cursor', cursor);
  return `/auditoria?${query}`;
}

export default async function AuditPage({
  searchParams,
}: {
  searchParams: Promise<Query>;
}) {
  const session = await readSession();
  if (!session) redirect('/entrar');

  let me;
  try {
    me = await fetchMe(session.token);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    throw error;
  }

  const filter = parseAuditFilter(await searchParams, me.companies);
  let snapshots;
  try {
    snapshots = await loadAuditCenter(session.token, me.companies, filter);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    throw error;
  }
  const entries = auditEntries(snapshots);
  const partial = snapshots.filter((item) => item.access !== 'available');
  const truncated = snapshots.filter((item) => item.hasMore);
  const counts = entries.reduce((result, item) => {
    result[item.event.outcome] = (result[item.event.outcome] ?? 0) + 1;
    return result;
  }, {} as Record<string, number>);
  const selected = filter.companyId ? snapshots[0] : null;

  return (
    <main>
      <header className="bar">
        <div>
          <Link href="/empresas">← Portafolio</Link>
          <h1>Accesos y auditoria</h1>
          <span className="who">{me.display_name}</span>
        </div>
        <SignOut />
      </header>

      <p className="lede">
        Actividad append-only consultada empresa por empresa. Muestra metadatos
        operativos, no valores de documentos, importes ni una certificacion legal.
      </p>

      <form className="card filter-form" method="get" aria-label="Filtrar auditoria">
        <label>
          Empresa
          <select name="empresa" defaultValue={filter.companyId ?? ''}>
            <option value="">Todas las visibles</option>
            {me.companies.map((company) => (
              <option value={company.company_id} key={company.company_id}>
                {company.legal_name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Resultado
          <select name="resultado" defaultValue={filter.outcome}>
            <option value="all">Todos</option>
            <option value="allowed">Permitidos</option>
            <option value="denied">Denegados</option>
            <option value="error">Errores</option>
          </select>
        </label>
        <label>
          Accion exacta
          <input name="accion" defaultValue={filter.action}
            placeholder="document.upload" maxLength={100} />
        </label>
        <label>
          Tipo de recurso
          <input name="recurso" defaultValue={filter.resourceKind}
            placeholder="document" maxLength={100} />
        </label>
        <button type="submit">Aplicar filtros</button>
      </form>

      {partial.length ? (
        <section className="notice" role="status">
          <strong>Vista parcial.</strong> {partial.length} empresa(s) están
          restringidas, revocadas o no disponibles. No se presentan como cero.
        </section>
      ) : null}
      {!filter.companyId && truncated.length ? (
        <section className="notice" role="status">
          {truncated.length} empresa(s) tienen más eventos. Selecciona una empresa
          para recorrer su historial completo con cursor estable.
        </section>
      ) : null}

      <dl className="metric-grid">
        <div><dt>Visibles</dt><dd>{entries.length}</dd></div>
        <div><dt>Permitidos</dt><dd>{counts.allowed ?? 0}</dd></div>
        <div><dt>Denegados</dt><dd>{counts.denied ?? 0}</dd></div>
        <div><dt>Errores</dt><dd>{counts.error ?? 0}</dd></div>
      </dl>

      {entries.length === 0 ? (
        <p className="card" role="status">
          No hay eventos visibles para estos filtros. Esto no demuestra ausencia
          de actividad en empresas restringidas o no disponibles.
        </p>
      ) : (
        <div className="card scroll">
          <table>
            <caption className="meta">
              Eventos ordenados por instante e identificador, del más reciente al más antiguo.
            </caption>
            <thead><tr>
              <th scope="col">Cuándo</th><th scope="col">Empresa</th>
              <th scope="col">Actor</th><th scope="col">Acción</th>
              <th scope="col">Recurso</th><th scope="col">Resultado</th>
            </tr></thead>
            <tbody>
              {entries.map(({ company, event }) => (
                <tr key={`${company.company_id}:${event.audit_event_id}`}>
                  <th scope="row" className="when">{when(event.occurred_at)}</th>
                  <td>{company.legal_name}</td><td>{event.actor_name}</td>
                  <td><code>{event.action}</code></td>
                  <td>{event.resource_kind}</td>
                  <td><span className={`outcome ${event.outcome}`}>
                    {OUTCOME_LABEL[event.outcome] ?? event.outcome}
                  </span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selected?.hasMore && selected.nextCursor ? (
        <nav className="pagination" aria-label="Paginas de auditoria">
          <Link href={nextHref(filter, selected.nextCursor)}>Eventos anteriores →</Link>
        </nav>
      ) : null}
    </main>
  );
}

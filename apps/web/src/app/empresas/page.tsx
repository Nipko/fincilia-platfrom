import Link from 'next/link';
import { redirect } from 'next/navigation';

import { ApiError, fetchMe } from '@/lib/api';
import { readSession } from '@/lib/session';
import { SignOut } from './sign-out';

export const dynamic = 'force-dynamic';

export default async function CompaniesPage() {
  const session = await readSession();
  if (!session) {
    redirect('/entrar');
  }

  let me;
  try {
    me = await fetchMe(session.token);
  } catch (error) {
    // Un token caducado o invalidado por una revocacion no es un error de la
    // interfaz: es una sesion que termino. Se vuelve a pedir entrar.
    if (error instanceof ApiError && error.status === 401) {
      redirect('/entrar');
    }
    throw error;
  }

  return (
    <main>
      <header className="bar">
        <div>
          <h1>Empresas</h1>
          <span className="who">{me.display_name}</span>
        </div>
        <SignOut />
      </header>

      {me.companies.length === 0 ? (
        <p className="card">
          No hay ninguna empresa con acceso vigente para esta cuenta.
        </p>
      ) : (
        <ul className="companies">
          {me.companies.map((company) => (
            <li key={company.company_id}>
              <Link href={`/empresas/${company.company_id}`}>
                <div className="card">
                  <div className="company-name">{company.legal_name}</div>
                  <div className="meta">
                    {company.country_code} · {company.status}
                  </div>
                  <div className="tags">
                    {company.roles.map((role) => (
                      <span className="tag" key={role}>
                        {role}
                      </span>
                    ))}
                  </div>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}

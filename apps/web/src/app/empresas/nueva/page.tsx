import { randomUUID } from 'node:crypto';

import Link from 'next/link';
import { redirect } from 'next/navigation';

import { ApiError, fetchManageableFirms } from '@/lib/api';
import { readSession } from '@/lib/session';

import { CompanyForm } from './company-form';

export const dynamic = 'force-dynamic';

export default async function NewCompanyPage() {
  const session = await readSession();
  if (!session) redirect('/entrar');

  let firms;
  try {
    firms = await fetchManageableFirms(session.token);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    throw error;
  }

  const now = new Date();
  const monthAnchor = `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1)
    .padStart(2, '0')}-01`;

  return (
    <main>
      <header className="bar">
        <div>
          <h1>Nueva empresa</h1>
          <span className="who">Alta completa y transaccional</span>
        </div>
        <Link href="/empresas">Volver al portafolio</Link>
      </header>

      <p className="lede">
        Crea la empresa, la delegacion de la firma y tu acceso owner en una sola
        operacion. Puedes dejar lista tambien la primera cuenta, fuente y ciclo.
      </p>

      <p className="notice" id="synthetic-company-notice">
        Entorno local: usa exclusivamente nombres e identificadores sinteticos.
        La identificacion tributaria y la cuenta se convierten en huellas con
        clave; no vuelven a mostrarse ni se guardan en claro.
      </p>

      {firms.length === 0 ? (
        <section className="card" aria-labelledby="sin-firma">
          <h2 id="sin-firma">No puedes crear empresas</h2>
          <p>Tu membresia actual no es owner ni administradora de una firma activa.</p>
        </section>
      ) : (
        <CompanyForm
          firms={firms}
          idempotencyKey={`fnc-web-${randomUUID()}`}
          monthAnchor={monthAnchor}
        />
      )}
    </main>
  );
}

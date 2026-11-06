import Link from 'next/link';
import { notFound, redirect } from 'next/navigation';

import {
  ApiError,
  fetchCompany,
  fetchOperatingProfile,
  type OperatingProfileState,
} from '@/lib/api';
import { formatReviewTimestamp } from '@/lib/review-inbox';
import { readSession } from '@/lib/session';
import { PROFILE_DESCRIPTIONS, PROFILE_LABELS } from '@/lib/simple-mode';
import { OperatingProfileForm } from './profile-form';

export const dynamic = 'force-dynamic';

function Denied() {
  return (
    <main className="page-state page-state--denied">
      <p className="page-state__label">Acceso restringido</p>
      <h1>Ajustes no disponibles</h1>
      <p className="page-state__description">
        Esta cuenta no tiene acceso vigente a la empresa solicitada.
      </p>
      <p className="page-state__action"><Link href="/empresas">Volver a empresas</Link></p>
    </main>
  );
}

export default async function CompanySettingsPage({
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

  let profile: OperatingProfileState | null = null;
  try {
    profile = await fetchOperatingProfile(session.token, companyId);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    if (error instanceof ApiError && error.status === 403) return <Denied />;
    profile = null;
  }

  return (
    <main>
      <header className="bar">
        <div>
          <p className="meta">{company.legal_name}</p>
          <h1>Ajustes de la empresa</h1>
        </div>
        <nav aria-label="Navegacion de ajustes">
          <Link href={`/empresas/${companyId}`}>Volver a la empresa</Link>
        </nav>
      </header>

      <section className="card" aria-labelledby="operating-profile-heading">
        <h2 id="operating-profile-heading">Perfil operativo</h2>
        {profile === null ? (
          <p className="notice" role="status">
            No se pudo consultar el perfil en este momento. No se presenta un
            valor supuesto.
          </p>
        ) : (
          <>
            <p>
              Perfil actual: <strong>{PROFILE_LABELS[profile.operating_profile]}</strong>.{' '}
              {PROFILE_DESCRIPTIONS[profile.operating_profile]}
            </p>
            {profile.can_change ? (
              <OperatingProfileForm companyId={companyId}
                current={profile.operating_profile} />
            ) : (
              <p className="meta" role="note">
                Solo el dueño de la empresa puede cambiar el perfil. Tu acceso es de
                consulta.
              </p>
            )}

            <h3>Historial de cambios</h3>
            {profile.history.length === 0 ? (
              <p className="meta">Aún no hay cambios registrados.</p>
            ) : (
              <ol className="profile-history" aria-label="Historial del perfil operativo">
                {profile.history.map((change) => (
                  <li key={change.change_id}>
                    <strong>
                      {PROFILE_LABELS[change.from_profile]} → {PROFILE_LABELS[change.to_profile]}
                    </strong>{' '}
                    por {change.changed_by_name} · {formatReviewTimestamp(change.changed_at)}
                    <div className="meta">Motivo: {change.reason}</div>
                  </li>
                ))}
              </ol>
            )}
          </>
        )}
      </section>
    </main>
  );
}

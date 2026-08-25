import Link from 'next/link';
import { notFound, redirect } from 'next/navigation';

import {
  ApiError,
  fetchCompany,
  fetchMe,
  fetchMembers,
  type CompanyMember,
} from '@/lib/api';
import { readSession } from '@/lib/session';
import { GrantRoleForm, RevokeRoleForm } from './role-forms';
import { ROLE_LABELS } from './roles';

export const dynamic = 'force-dynamic';

const ALL_ROLES = ['owner', 'firm_admin', 'preparer', 'reviewer', 'auditor', 'read_only'];
const PRIVILEGED_ROLES = new Set(['owner', 'firm_admin']);

function Denied() {
  return (
    <main className="page-state page-state--denied">
      <p className="page-state__label">Acceso restringido</p>
      <h1>Equipo no disponible</h1>
      <p className="page-state__description">
        Esta cuenta no administra los accesos de la empresa solicitada.
      </p>
      <p className="page-state__action"><Link href="/empresas">Volver a empresas</Link></p>
    </main>
  );
}

export default async function TeamPage({
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
  if (!company.permissions.includes('member.manage')) return <Denied />;

  let members: CompanyMember[];
  let me;
  try {
    [members, me] = await Promise.all([
      fetchMembers(session.token, companyId),
      fetchMe(session.token),
    ]);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect('/entrar');
    if (error instanceof ApiError && error.status === 403) return <Denied />;
    throw error;
  }

  const isOwner = company.roles.includes('owner');
  const assignableRoles = isOwner
    ? ALL_ROLES
    : ALL_ROLES.filter((role) => !PRIVILEGED_ROLES.has(role));

  return (
    <main>
      <header className="bar">
        <div>
          <p className="meta">{company.legal_name}</p>
          <h1>Equipo y roles</h1>
        </div>
        <nav aria-label="Navegacion del equipo">
          <Link href={`/empresas/${companyId}`}>Volver a la empresa</Link>{' '}
          <Link href="/empresas">Empresas</Link>
        </nav>
      </header>

      <section className="card team-guidance" aria-labelledby="role-guidance-title">
        <h2 id="role-guidance-title">Acceso acumulable, decisiones separadas</h2>
        <p>
          Una persona puede cumplir varios roles. La API conserva la segregacion por
          objeto: quien preparo un expediente no puede aprobar su propio trabajo aunque
          tambien tenga rol de revisor.
        </p>
        <p className="meta">
          Las identidades se crean en el proveedor de identidad. Aqui solo se conceden
          o revocan accesos para esta empresa; no se crean contrasenas.
        </p>
      </section>

      <section aria-label="Miembros activos" className="member-list">
        {members.map((member) => {
          const isSelf = member.subject_id === me.subject_id;
          const available = isSelf
            ? []
            : assignableRoles.filter((role) => !member.company_roles.includes(role));
          const revocable = member.company_roles.filter(
            (role) => isOwner || !PRIVILEGED_ROLES.has(role),
          );
          return (
            <article className="card member-card" key={member.subject_id}>
              <header className="member-card__header">
                <div>
                  <h2>{member.display_name}{isSelf ? ' (tu cuenta)' : ''}</h2>
                  <p className="meta">Membresia en la firma: {member.firm_role}</p>
                </div>
                <div className="tags" aria-label={`Roles de ${member.display_name}`}>
                  {member.company_roles.length ? member.company_roles.map((role) => (
                    <span className="tag" key={role}>{ROLE_LABELS[role] ?? role}</span>
                  )) : <span className="tag tag--muted">Sin acceso a esta empresa</span>}
                </div>
              </header>

              {!isSelf ? (
                <GrantRoleForm
                  companyId={companyId}
                  subjectId={member.subject_id}
                  displayName={member.display_name}
                  availableRoles={available}
                />
              ) : (
                <p className="meta">No puedes concederte permisos a ti mismo.</p>
              )}

              {revocable.length ? (
                <details className="member-revoke">
                  <summary>Revocar un rol activo</summary>
                  <div className="member-revoke__forms">
                    {revocable.map((role) => (
                      <RevokeRoleForm
                        key={role}
                        companyId={companyId}
                        subjectId={member.subject_id}
                        displayName={member.display_name}
                        role={role}
                      />
                    ))}
                  </div>
                </details>
              ) : null}
            </article>
          );
        })}
      </section>
    </main>
  );
}

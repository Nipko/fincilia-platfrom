'use client';

import { useActionState } from 'react';

import {
  grantMemberRoleAction,
  revokeMemberRoleAction,
  type RoleManagementState,
} from '@/app/actions';
import { ROLE_LABELS } from './roles';

const INITIAL: RoleManagementState = { error: null, done: null };

const REASONS = [
  { id: 'access_required', label: 'Necesita acceso para su responsabilidad' },
  { id: 'responsibility_change', label: 'Cambio de responsabilidad' },
  { id: 'team_change', label: 'Cambio en el equipo' },
  { id: 'least_privilege', label: 'Aplicar minimo privilegio' },
  { id: 'access_removed', label: 'Retirar acceso' },
] as const;

function Feedback({ state }: { state: RoleManagementState }) {
  if (state.error) return <p className="notice error" role="alert">{state.error}</p>;
  if (state.done) return <p className="notice ok" role="status">{state.done}</p>;
  return null;
}

export function GrantRoleForm({
  companyId,
  subjectId,
  displayName,
  availableRoles,
}: {
  companyId: string;
  subjectId: string;
  displayName: string;
  availableRoles: string[];
}) {
  const [state, action, pending] = useActionState(grantMemberRoleAction, INITIAL);
  if (availableRoles.length === 0) {
    return <p className="meta">No hay otros roles que puedas asignar.</p>;
  }
  return (
    <form className="member-role-form" action={action}>
      <input type="hidden" name="companyId" value={companyId} />
      <input type="hidden" name="subjectId" value={subjectId} />
      <label>
        Nuevo rol para {displayName}
        <select name="role" defaultValue={availableRoles[0]} required>
          {availableRoles.map((role) => (
            <option key={role} value={role}>{ROLE_LABELS[role] ?? role}</option>
          ))}
        </select>
      </label>
      <label>
        Motivo
        <select name="reasonCode" defaultValue="access_required" required>
          {REASONS.map((reason) => (
            <option key={reason.id} value={reason.id}>{reason.label}</option>
          ))}
        </select>
      </label>
      <button type="submit" disabled={pending}>
        {pending ? 'Asignando...' : 'Asignar rol'}
      </button>
      <Feedback state={state} />
    </form>
  );
}

export function RevokeRoleForm({
  companyId,
  subjectId,
  displayName,
  role,
}: {
  companyId: string;
  subjectId: string;
  displayName: string;
  role: string;
}) {
  const [state, action, pending] = useActionState(revokeMemberRoleAction, INITIAL);
  return (
    <form className="member-revoke-form" action={action}>
      <input type="hidden" name="companyId" value={companyId} />
      <input type="hidden" name="subjectId" value={subjectId} />
      <input type="hidden" name="role" value={role} />
      <label>
        Motivo para revocar {ROLE_LABELS[role] ?? role} de {displayName}
        <select name="reasonCode" defaultValue="access_removed" required>
          {REASONS.map((reason) => (
            <option key={reason.id} value={reason.id}>{reason.label}</option>
          ))}
        </select>
      </label>
      <button type="submit" className="secondary" disabled={pending}>
        {pending ? 'Revocando...' : `Revocar ${ROLE_LABELS[role] ?? role}`}
      </button>
      <Feedback state={state} />
    </form>
  );
}

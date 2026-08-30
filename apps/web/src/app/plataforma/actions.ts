'use server';

import { revalidatePath } from 'next/cache';

import {
  grantPlatformRole,
  revokePlatformRole,
  setPlatformIdentityStatus,
  type PlatformRole,
} from '@/lib/api';
import { readSession } from '@/lib/session';

export async function changeIdentityStatus(formData: FormData): Promise<void> {
  const session = await readSession();
  if (!session) throw new Error('authentication required');
  const subjectId = String(formData.get('subject_id') ?? '');
  const status = String(formData.get('status') ?? '');
  if (!/^[0-9a-f-]{36}$/.test(subjectId)
      || (status !== 'active' && status !== 'suspended')) {
    throw new Error('invalid platform status request');
  }
  await setPlatformIdentityStatus(
    session.token, subjectId, status, 'platform_console_status_change',
  );
  revalidatePath('/plataforma');
}

const PLATFORM_ROLES = new Set<PlatformRole>([
  'platform_superadmin', 'platform_operator', 'platform_auditor',
]);

export async function grantRole(formData: FormData): Promise<void> {
  const session = await readSession();
  if (!session) throw new Error('authentication required');
  const subjectId = String(formData.get('subject_id') ?? '');
  const role = String(formData.get('platform_role') ?? '') as PlatformRole;
  if (!/^[0-9a-f-]{36}$/.test(subjectId) || !PLATFORM_ROLES.has(role)) {
    throw new Error('invalid platform role request');
  }
  await grantPlatformRole(
    session.token, subjectId, role, 'platform_console_role_grant',
  );
  revalidatePath('/plataforma');
}

export async function revokeRole(formData: FormData): Promise<void> {
  const session = await readSession();
  if (!session) throw new Error('authentication required');
  const subjectId = String(formData.get('subject_id') ?? '');
  const role = String(formData.get('platform_role') ?? '') as PlatformRole;
  if (!/^[0-9a-f-]{36}$/.test(subjectId) || !PLATFORM_ROLES.has(role)) {
    throw new Error('invalid platform role request');
  }
  await revokePlatformRole(
    session.token, subjectId, role, 'platform_console_role_revoke',
  );
  revalidatePath('/plataforma');
}

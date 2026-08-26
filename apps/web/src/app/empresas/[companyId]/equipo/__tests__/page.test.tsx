import { render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('server-only', () => ({}));

const mocks = vi.hoisted(() => ({
  fetchCompany: vi.fn(),
  fetchMe: vi.fn(),
  fetchMembers: vi.fn(),
  readSession: vi.fn(),
  redirect: vi.fn((): never => { throw new Error('NEXT_REDIRECT'); }),
  notFound: vi.fn((): never => { throw new Error('NEXT_NOT_FOUND'); }),
}));

vi.mock('next/navigation', () => ({
  redirect: mocks.redirect,
  notFound: mocks.notFound,
}));
vi.mock('@/lib/session', () => ({ readSession: mocks.readSession }));
vi.mock('@/app/actions', () => ({
  grantMemberRoleAction: vi.fn(),
  revokeMemberRoleAction: vi.fn(),
}));
vi.mock('@/lib/api', () => ({
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
  fetchCompany: mocks.fetchCompany,
  fetchMe: mocks.fetchMe,
  fetchMembers: mocks.fetchMembers,
}));

import TeamPage from '../page';

const COMPANY = '161b0037-c445-50aa-b400-72632d3f53f0';
const SOFIA = '11111111-1111-4111-8111-111111111111';
const CARLA = '22222222-2222-4222-8222-222222222222';

describe('TeamPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.readSession.mockResolvedValue({ token: 'synthetic-token' });
    mocks.fetchMe.mockResolvedValue({ subject_id: SOFIA });
    mocks.fetchCompany.mockResolvedValue({
      legal_name: 'Panaderia La Espiga SAS',
      permissions: ['member.manage'],
      roles: ['owner'],
    });
    mocks.fetchMembers.mockResolvedValue([
      {
        subject_id: SOFIA,
        display_name: 'Sofia Owner',
        firm_role: 'owner',
        company_roles: ['owner'],
      },
      {
        subject_id: CARLA,
        display_name: 'Carla Auditora',
        firm_role: 'member',
        company_roles: [],
      },
    ]);
  });

  it('muestra miembros sin datos de identidad y permite roles multiples', async () => {
    render(await TeamPage({ params: Promise.resolve({ companyId: COMPANY }) }));

    expect(screen.getByRole('heading', { name: 'Equipo y roles' })).toBeInTheDocument();
    expect(screen.getByText(/no se crean contrasenas/i)).toBeInTheDocument();
    expect(screen.queryByText(/@demo\.local/)).not.toBeInTheDocument();
    const carla = screen.getByRole('heading', { name: 'Carla Auditora' })
      .closest('article');
    expect(carla).not.toBeNull();
    expect(screen.getByRole('option', { name: 'Owner de empresa' })).toBeInTheDocument();
    expect(within(carla!).getByRole('button', { name: 'Asignar rol' })).toBeInTheDocument();
  });

  it('no ofrece autopermiso a la cuenta activa', async () => {
    render(await TeamPage({ params: Promise.resolve({ companyId: COMPANY }) }));

    expect(screen.getByText('No puedes concederte permisos a ti mismo.'))
      .toBeInTheDocument();
  });

  it('oculta roles privilegiados a firm_admin', async () => {
    mocks.fetchCompany.mockResolvedValue({
      legal_name: 'Panaderia La Espiga SAS',
      permissions: ['member.manage'],
      roles: ['firm_admin'],
    });

    render(await TeamPage({ params: Promise.resolve({ companyId: COMPANY }) }));

    expect(screen.queryByRole('option', { name: 'Owner de empresa' }))
      .not.toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Administrador de firma' }))
      .not.toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Preparador' })).toBeInTheDocument();
  });

  it('no consulta el directorio cuando falta member.manage', async () => {
    mocks.fetchCompany.mockResolvedValue({
      legal_name: 'Panaderia La Espiga SAS',
      permissions: ['movement.read'],
      roles: ['reviewer'],
    });

    render(await TeamPage({ params: Promise.resolve({ companyId: COMPANY }) }));

    expect(screen.getByRole('heading', { name: 'Equipo no disponible' }))
      .toBeInTheDocument();
    expect(mocks.fetchMembers).not.toHaveBeenCalled();
  });
});

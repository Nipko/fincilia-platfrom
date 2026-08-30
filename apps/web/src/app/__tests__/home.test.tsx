import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  managedOidcRegistrationEnabled: vi.fn(),
  readSession: vi.fn(),
}));

vi.mock('@/lib/managed-oidc', () => ({
  managedOidcRegistrationEnabled: mocks.managedOidcRegistrationEnabled,
}));
vi.mock('@/lib/session', () => ({ readSession: mocks.readSession }));

import Home from '../page';

describe('Home', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.readSession.mockResolvedValue(null);
    mocks.managedOidcRegistrationEnabled.mockReturnValue(false);
  });

  it('describe la invitación sintética cuando Google está apagado', async () => {
    render(await Home());

    expect(screen.getByText(
      'Entorno UAT · identidad administrada pendiente de activación.',
    )).toBeInTheDocument();
    expect(screen.queryByText(/Registro público con Google/)).not.toBeInTheDocument();
  });

  it('solo anuncia registro Google cuando el modo público está habilitado', async () => {
    mocks.managedOidcRegistrationEnabled.mockReturnValue(true);

    render(await Home());

    expect(screen.getByText(
      'Registro público con Google · datos reales pendientes de autorización.',
    )).toBeInTheDocument();
  });
});

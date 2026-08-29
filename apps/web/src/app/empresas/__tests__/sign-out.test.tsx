import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../actions', () => ({ signOutAction: vi.fn() }));

import { SignOut } from '../sign-out';

describe('control de cierre de sesion', () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllEnvs();
  });

  it('usa el endpoint federado solo cuando OIDC esta habilitado', () => {
    vi.stubEnv('FINCILIA_OIDC_ENABLED', 'true');
    render(<SignOut />);
    expect(screen.getByRole('button', { name: 'Salir' }).closest('form'))
      .toHaveAttribute('action', '/api/auth/oidc/logout');
  });

  it('conserva la accion local en el laboratorio sintetico', () => {
    vi.stubEnv('FINCILIA_OIDC_ENABLED', 'false');
    render(<SignOut />);
    expect(screen.getByRole('button', { name: 'Salir' }).closest('form'))
      .not.toHaveAttribute('action', '/api/auth/oidc/logout');
  });
});

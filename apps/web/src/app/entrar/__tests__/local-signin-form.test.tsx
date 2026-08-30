import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../../actions', () => ({
  signInAction: vi.fn(),
}));

import { LocalSignInForm } from '../local-signin-form';

describe('LocalSignInForm', () => {
  it('no publica identidades conocidas fuera del entorno local', () => {
    render(<LocalSignInForm showDemoAccounts={false} />);

    expect(screen.getByLabelText('Usuario')).toHaveAttribute(
      'placeholder', 'usuario@demo.local');
    expect(screen.getByLabelText('Usuario')).toHaveValue('');
    expect(screen.queryByText('Ver cuentas de demostracion')).not.toBeInTheDocument();
    expect(screen.queryByText('ana@demo.local')).not.toBeInTheDocument();
  });

  it('conserva la ayuda de desarrollo en el entorno local', () => {
    render(<LocalSignInForm showDemoAccounts />);

    expect(screen.getByLabelText('Usuario')).toHaveValue('ana@demo.local');
    expect(screen.getByText('Ver cuentas de demostracion')).toBeInTheDocument();
  });
});

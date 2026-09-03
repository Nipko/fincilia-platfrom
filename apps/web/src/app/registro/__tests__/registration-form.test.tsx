import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../../actions', () => ({
  registerAccountAction: vi.fn(),
}));

import { RegistrationForm } from '../registration-form';

describe('RegistrationForm', () => {
  it('solicita términos y autorización de privacidad separados en el alta Google', () => {
    render(
      <RegistrationForm
        inviteRequired={false}
        managedIdentity
        managedError={false}
      />,
    );

    expect(screen.getByRole('checkbox', { name: /Acepto los terminos del servicio/i }))
      .toBeRequired();
    expect(screen.getByRole('checkbox', {
      name: /Autorizo a Parallext LLC a tratar mis datos de cuenta/i,
    })).toBeRequired();
    expect(screen.getByRole('link', { name: 'terminos del servicio' }))
      .toHaveAttribute('href', '/terminos');
    expect(screen.getByRole('link', { name: 'politica de privacidad' }))
      .toHaveAttribute('href', '/privacidad');
  });
});

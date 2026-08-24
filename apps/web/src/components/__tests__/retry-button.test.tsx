import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { RetryButton } from '../retry-button';

describe('RetryButton', () => {
  it('ejecuta un unico reintento explicito', async () => {
    const user = userEvent.setup();
    const retry = vi.fn();

    render(<RetryButton onRetry={retry} />);
    await user.click(screen.getByRole('button', { name: 'Intentar de nuevo' }));

    expect(retry).toHaveBeenCalledOnce();
  });

  it('permite un nombre accesible contextual', () => {
    render(<RetryButton label="Reintentar carga" onRetry={() => undefined} />);

    expect(
      screen.getByRole('button', { name: 'Reintentar carga' }),
    ).toBeEnabled();
  });
});

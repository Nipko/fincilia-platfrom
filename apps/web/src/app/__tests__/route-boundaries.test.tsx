import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import ErrorPage from '../error';
import Loading from '../loading';
import NotFound from '../not-found';

describe('fronteras globales de ruta', () => {
  it('muestra una carga identificable', () => {
    render(<Loading />);

    expect(
      screen.getByRole('status', { name: 'Cargando información' }),
    ).toHaveAttribute('aria-busy', 'true');
  });

  it('permite reintentar sin revelar el detalle interno del error', async () => {
    const user = userEvent.setup();
    const reset = vi.fn();
    const internalDetail = 'detalle-interno-sintetico-no-visible';

    render(
      <ErrorPage
        error={Object.assign(new Error(internalDetail), {
          digest: 'digest-sintetico',
        })}
        reset={reset}
      />,
    );

    expect(screen.queryByText(internalDetail)).not.toBeInTheDocument();
    expect(screen.queryByText('digest-sintetico')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Intentar de nuevo' }));
    expect(reset).toHaveBeenCalledOnce();
  });

  it('ofrece una salida navegable desde no encontrado', () => {
    render(<NotFound />);

    expect(
      screen.getByRole('heading', {
        level: 1,
        name: 'No encontramos esta página',
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Volver al inicio' })).toHaveAttribute(
      'href',
      '/',
    );
  });
});

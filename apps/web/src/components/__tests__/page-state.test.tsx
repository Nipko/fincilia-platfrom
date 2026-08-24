import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { PageState } from '../page-state';

describe('PageState', () => {
  it('anuncia de forma asertiva una denegacion y conserva la accion', () => {
    render(
      <PageState
        action={<button type="button">Volver</button>}
        description="La cuenta sintetica no tiene acceso vigente."
        kind="denied"
        title="Sin acceso"
      />,
    );

    const alert = screen.getByRole('alert', { name: 'Sin acceso' });
    expect(alert).toHaveAttribute('aria-live', 'assertive');
    expect(alert).toHaveTextContent('Acceso denegado');
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent(
      'Sin acceso',
    );
    expect(screen.getByRole('button', { name: 'Volver' })).toBeEnabled();
  });

  it('expone la carga como estado ocupado y no como alerta', () => {
    render(
      <PageState
        description="Preparando la vista sintetica."
        headingAs="h1"
        kind="loading"
        title="Cargando informacion"
      />,
    );

    const status = screen.getByRole('status', {
      name: 'Cargando informacion',
    });
    expect(status).toHaveAttribute('aria-busy', 'true');
    expect(status).toHaveAttribute('aria-live', 'polite');
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Cargando informacion',
    );
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('distingue un vacio exitoso de una degradacion', () => {
    const { rerender } = render(
      <PageState
        description="La respuesta autorizada no contiene elementos."
        kind="empty"
        title="Todavia no hay documentos"
      />,
    );

    expect(screen.getByRole('status')).toHaveTextContent('Sin resultados');

    rerender(
      <PageState
        description="El servicio no respondio."
        kind="degraded"
        title="Temporalmente no disponible"
      />,
    );

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Servicio no disponible',
    );
  });
});

import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('next/navigation', () => ({ usePathname: () => '/plataforma' }));

import { GlobalNavigation } from '../global-navigation';

describe('GlobalNavigation', () => {
  it('solo muestra el plano de control cuando el servidor devolvió autoridad', () => {
    const { rerender } = render(
      <GlobalNavigation authenticated displayName="Founder" platformAccess={false} />,
    );
    expect(screen.queryByRole('link', { name: /Control central/ })).not.toBeInTheDocument();

    rerender(
      <GlobalNavigation authenticated displayName="Founder" platformAccess />,
    );
    expect(screen.getByRole('link', { name: /Control central/ })).toHaveAttribute(
      'href', '/plataforma',
    );
  });
});

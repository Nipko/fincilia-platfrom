import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { BrandMark } from '@/components/brand-mark';

describe('BrandMark', () => {
  it('expone la marca y mantiene el inicio como destino accesible', () => {
    const { container } = render(<BrandMark />);

    expect(screen.getByRole('link', { name: 'Fincilia, ir al inicio' })).toHaveAttribute('href', '/');
    expect(screen.getByText('Fincilia')).toBeInTheDocument();
    expect(screen.getByText('Conciliación clara')).toBeInTheDocument();
    expect(container.querySelector('.brand-mark__sheet')).toBeInTheDocument();
    expect(container.querySelector('.brand-mark__match')).toBeInTheDocument();
  });
});

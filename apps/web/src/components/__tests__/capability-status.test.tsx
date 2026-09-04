import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { CapabilityStatus } from '../capability-status';

describe('CapabilityStatus', () => {
  it('explica el estado sin depender solo del color', () => {
    render(<CapabilityStatus state="blocked" title="OCR"
      description="No se transmite fuera de Fincilia." detail={<span>Requiere proveedor</span>} />);

    expect(screen.getByRole('heading', { name: 'OCR' })).toBeInTheDocument();
    expect(screen.getByText('No habilitado')).toHaveAttribute('data-state', 'blocked');
    expect(screen.getByText('Requiere proveedor')).toBeInTheDocument();
  });
});

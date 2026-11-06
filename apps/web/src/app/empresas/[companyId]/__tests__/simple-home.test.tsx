import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('@/app/actions', () => ({
  certifyAccountingPeriodAction: vi.fn(),
}));

import type { AccountingPeriodClose } from '@/lib/api';
import { SimpleHome } from '../simple-home';

const COMPANY = '161b0037-c445-50aa-b400-72632d3f53f0';
const OWNER = '11111111-1111-4111-8111-111111111111';
const ACCOUNTANT = '22222222-2222-4222-8222-222222222222';

const selfReviewedClose = {
  close_id: '33333333-3333-4333-8333-333333333333',
  period_start: '2026-09-01',
  period_end: '2026-09-30',
  version: 1,
  closed_by: OWNER,
  closer_name: 'Dueña Sintetica',
  status: 'closed',
  certification: 'self_reviewed',
  certification_record: null,
} as unknown as AccountingPeriodClose;

describe('SimpleHome', () => {
  it('muestra tres pasos y mantiene el modo contador accesible', () => {
    render(
      <SimpleHome companyId={COMPANY} actorId={OWNER}
        permissions={['movement.read', 'report.read', 'close.approve']}
        upload={<p>Formulario de carga</p>}
        pending={[]} pendingPartial={false} close={selfReviewedClose} />,
    );

    expect(screen.getByRole('heading', { level: 3, name: 'Subir' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 3, name: 'Revisar pendientes' }))
      .toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 3, name: 'Listo' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Modo contador →' }))
      .toHaveAttribute('href', `/empresas/${COMPANY}/flujo-contable`);
    expect(screen.getByText('Cerrado — autorrevisado')).toBeInTheDocument();
    // Quien cerro no puede certificar su propio cierre.
    expect(screen.queryByRole('button', { name: 'Certificar cierre' })).toBeNull();
  });

  it('ofrece certificar a una segunda persona y muestra explicacion y modo', () => {
    render(
      <SimpleHome companyId={COMPANY} actorId={ACCOUNTANT}
        permissions={['movement.read', 'report.read', 'close.approve']}
        upload={null}
        pending={[{
          key: 'candidate:1', kind: 'candidate', title: 'Posible cruce por confirmar',
          detail: 'Propuesto por Dueña', explanation: ['Mismo NIT del pagador.'],
          reviewMode: 'approved_rule', href: '/empresas/x/conciliacion',
        }]}
        pendingPartial={false} close={selfReviewedClose} />,
    );

    expect(screen.getByRole('button', { name: 'Certificar cierre' })).toBeInTheDocument();
    expect(screen.getByText('Mismo NIT del pagador.')).toBeInTheDocument();
    expect(screen.getByText('Regla aprobada')).toBeInTheDocument();
  });
});

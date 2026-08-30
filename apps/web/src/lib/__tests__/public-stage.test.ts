import { describe, expect, it } from 'vitest';

import { demoAccountsVisible, publicStage } from '../public-stage';

describe('publicStage', () => {
  it('presenta el sistema definitivo sin llamarlo beta ni abrir datos reales', () => {
    expect(publicStage('preproduction')).toEqual({
      badge: 'Preproducción',
      footer: 'Preproducción · datos sintéticos',
    });
  });
  it('no presenta el piloto privado como entorno local ni autoautoriza datos', () => {
    expect(publicStage('private_pilot')).toEqual({
      badge: 'Piloto privado',
      footer: 'Piloto privado · acceso por invitación',
    });
  });

  it('mantiene la beta cerrada como sintetica', () => {
    expect(publicStage('closed_beta').footer).toContain('datos sintéticos');
  });

  it('falla a la etiqueta segura para valores desconocidos', () => {
    expect(publicStage('production')).toEqual({
      badge: 'Entorno local',
      footer: 'Entorno local · datos sintéticos',
    });
  });

  it('solo expone las cuentas conocidas de demostracion en desarrollo local', () => {
    expect(demoAccountsVisible(undefined)).toBe(true);
    expect(demoAccountsVisible('local')).toBe(true);
    expect(demoAccountsVisible('closed_beta')).toBe(false);
    expect(demoAccountsVisible('preproduction')).toBe(false);
    expect(demoAccountsVisible('production')).toBe(false);
  });
});

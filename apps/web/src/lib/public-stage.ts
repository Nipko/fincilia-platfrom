export type PublicStage = {
  badge: string;
  footer: string;
};

export function demoAccountsVisible(value: string | undefined): boolean {
  return value === undefined || value === 'local';
}

export function publicStage(value: string | undefined): PublicStage {
  if (value === 'uat') {
    return {
      badge: 'UAT',
      footer: 'Entorno UAT de validación previo a producción.',
    };
  }
  if (value === 'preproduction') {
    return { badge: 'Preproducción', footer: 'Preproducción · datos sintéticos' };
  }
  if (value === 'private_pilot') {
    return { badge: 'Piloto privado', footer: 'Piloto privado · acceso por invitación' };
  }
  if (value === 'closed_beta') {
    // Compatibilidad con la variable heredada del host. La experiencia y los
    // nuevos despliegues usan UAT; renombrar recursos físicos se hará con una
    // migración de estado, no destruyéndolos por estética.
    return { badge: 'UAT', footer: 'Entorno UAT de validación previo a producción.' };
  }
  return { badge: 'Entorno local', footer: 'Entorno local · datos sintéticos' };
}

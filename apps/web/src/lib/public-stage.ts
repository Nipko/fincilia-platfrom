export type PublicStage = {
  badge: string;
  footer: string;
};

export function publicStage(value: string | undefined): PublicStage {
  if (value === 'preproduction') {
    return { badge: 'Preproducción', footer: 'Preproducción · datos sintéticos' };
  }
  if (value === 'private_pilot') {
    return { badge: 'Piloto privado', footer: 'Piloto privado · acceso por invitación' };
  }
  if (value === 'closed_beta') {
    return { badge: 'Beta cerrada', footer: 'Beta cerrada · datos sintéticos' };
  }
  return { badge: 'Entorno local', footer: 'Entorno local · datos sintéticos' };
}

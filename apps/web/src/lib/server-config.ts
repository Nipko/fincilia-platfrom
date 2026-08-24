import 'server-only';

/**
 * Resuelve una ruta interna de la API sin publicar la base al navegador.
 *
 * Mantener esta lectura en un modulo `server-only` evita que una importacion
 * accidental desde un Client Component termine incorporando topologia interna
 * en el bundle que recibe la persona usuaria.
 */
export function apiUrl(path: string): string {
  const configured = process.env.FINCILIA_API_BASE_URL;
  if (!configured) {
    throw new Error('FINCILIA_API_BASE_URL is required');
  }
  const base = configured.replace(/\/+$/, '');
  const suffix = path.startsWith('/') ? path : `/${path}`;
  return `${base}${suffix}`;
}

/**
 * Origen publico opcional para despliegues con terminacion TLS o proxy inverso.
 * Si se configura, debe ser un origen HTTP(S) puro: sin ruta, credenciales,
 * query ni fragmento. Una configuracion ambigua falla cerrada al arrancar la
 * peticion que la necesita.
 */
export function publicWebOrigin(): string | null {
  const configured = process.env.FINCILIA_PUBLIC_ORIGIN;
  if (!configured) {
    return null;
  }
  const parsed = new URL(configured);
  if (
    (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') ||
    parsed.username !== '' ||
    parsed.password !== '' ||
    parsed.pathname !== '/' ||
    parsed.search !== '' ||
    parsed.hash !== ''
  ) {
    throw new Error('FINCILIA_PUBLIC_ORIGIN must be an HTTP(S) origin');
  }
  return parsed.origin;
}

/**
 * Contexto del recorrido fuente -> documento -> mapeo.
 *
 * Los nombres de query son parte de la URL visible; el resto de la aplicacion
 * usa estas propiedades para no volver a construirlos a mano y perder uno al
 * cambiar de pagina o version.
 */
export type FlowContext = {
  documento?: string | null;
  fuente?: string | null;
  mapeo?: string | null;
  dataset?: string | null;
  pagina?: number | null;
  movimientosPagina?: number | null;
  plantilla?: string | null;
};

// Evita offsets absurdos y garantiza que incluso la pagina de movimientos
// (50 filas) siga siendo un entero exacto. La API podra sustituir offset por
// cursor sin convertir una query hostil en una exploracion ilimitada.
export const MAX_NAVIGATION_PAGE = 10_000;

function nonEmpty(value: string | null | undefined): string | null {
  const candidate = value?.trim() ?? '';
  return candidate.length > 0 ? candidate : null;
}

export function singleQueryValue(
  value: string | string[] | undefined,
): string | null {
  return typeof value === 'string' ? nonEmpty(value) : null;
}

/** Construye una ruta interna conservando solo el contexto conocido. */
export function withFlowContext(pathname: string, context: FlowContext): string {
  const query = new URLSearchParams();
  const artifactId = nonEmpty(context.documento);
  const sourceId = nonEmpty(context.fuente);
  const mappingId = nonEmpty(context.mapeo);
  const datasetId = nonEmpty(context.dataset);
  const templateId = nonEmpty(context.plantilla);

  if (artifactId) {
    query.set('documento', artifactId);
  }
  if (sourceId) {
    query.set('fuente', sourceId);
  }
  if (mappingId) {
    query.set('mapeo', mappingId);
  }
  if (datasetId) {
    query.set('dataset', datasetId);
  }
  if (templateId) {
    query.set('plantilla', templateId);
  }
  if (
    context.pagina !== null &&
    context.pagina !== undefined &&
    Number.isSafeInteger(context.pagina) &&
    context.pagina >= 0
  ) {
    query.set('pagina', String(context.pagina));
  }
  if (
    context.movimientosPagina !== null &&
    context.movimientosPagina !== undefined &&
    Number.isSafeInteger(context.movimientosPagina) &&
    context.movimientosPagina >= 0
  ) {
    query.set('movimientosPagina', String(context.movimientosPagina));
  }

  const serialized = query.toString();
  return serialized ? `${pathname}?${serialized}` : pathname;
}

/**
 * Lee una pagina sin aceptar signos, decimales, notacion exponencial ni enteros
 * que JavaScript ya no pueda representar de forma exacta.
 */
export function pageFromQuery(value: string | string[] | undefined): number {
  if (typeof value !== 'string' || !value || !/^\d+$/.test(value)) {
    return 0;
  }
  const page = Number(value);
  return Number.isSafeInteger(page) && page <= MAX_NAVIGATION_PAGE ? page : 0;
}

export function selectMappingVersion(
  requestedId: string | null,
  hasExplicitSource: boolean,
  authorizedIds: readonly string[],
): { selectedId: string | null; invalidRequestedId: boolean } {
  if (requestedId !== null) {
    return authorizedIds.includes(requestedId)
      ? { selectedId: requestedId, invalidRequestedId: false }
      : { selectedId: null, invalidRequestedId: true };
  }
  // Un artefacto deduplicado puede tener mappings historicos de otra fuente.
  // Con fuente explicita se crea/elige conscientemente; nunca se toma el primero.
  return {
    selectedId: hasExplicitSource ? null : (authorizedIds[0] ?? null),
    invalidRequestedId: false,
  };
}

/** Una version historica explicita nunca se sustituye por "la mas reciente". */
export function selectDatasetVersion(
  requestedId: string | null,
  requested: boolean,
  authorizedIds: readonly string[],
): { selectedId: string | null; invalidRequestedId: boolean } {
  if (requested) {
    return requestedId !== null && authorizedIds.includes(requestedId)
      ? { selectedId: requestedId, invalidRequestedId: false }
      : { selectedId: null, invalidRequestedId: true };
  }
  return { selectedId: authorizedIds[0] ?? null, invalidRequestedId: false };
}

export type DocumentFormatCapability = Readonly<{
  id: 'csv' | 'xlsx' | 'ods' | 'pdf';
  label: string;
  state: 'available' | 'conditional';
  inspection: string;
  extraction: string;
  boundary: string;
}>;

export const DOCUMENT_FORMAT_CAPABILITIES: readonly DocumentFormatCapability[] = [
  {
    id: 'csv',
    label: 'CSV',
    state: 'available',
    inspection: 'Inspección completa y detección de codificación y delimitador.',
    extraction: 'Perfil, tipos, limpieza, mapeo y coordenada de fila/columna.',
    boundary: 'Archivos truncados, ambiguos o fuera de límites permanecen en cuarentena.',
  },
  {
    id: 'xlsx',
    label: 'Excel XLSX',
    state: 'conditional',
    inspection: 'Estructura OPC completa; macros, enlaces y contenido activo se rechazan.',
    extraction: 'Una hoja segura o selección explícita cuando existen varias.',
    boundary: 'Las fórmulas requieren revisión y nunca se ejecutan en Fincilia.',
  },
  {
    id: 'ods',
    label: 'OpenDocument ODS',
    state: 'conditional',
    inspection: 'Paquete tabular completo con límites y contenido activo bloqueado.',
    extraction: 'Selección, perfil, tipos y coordenadas sobre hojas seguras.',
    boundary: 'Documentos cifrados, firmados o ambiguos no se promueven.',
  },
  {
    id: 'pdf',
    label: 'PDF',
    state: 'conditional',
    inspection: 'PDF pasivo, no cifrado y sin acciones o contenido activo; OCR local aislado.',
    extraction: 'Texto embebido u OCR por página y bloque, con ubicación y revisión humana.',
    boundary: 'OCR local hasta 50 páginas; no transmite el documento a proveedores externos.',
  },
] as const;

export type QualityCoverage = Readonly<{
  code: string;
  label: string;
  scope: 'dataset' | 'movement';
  description: string;
}>;

export const QUALITY_RULE_COVERAGE: readonly QualityCoverage[] = [
  { code: 'dataset_completeness_mismatch', label: 'Conteos inconsistentes', scope: 'dataset',
    description: 'Compara registros esperados, almacenados y rechazados.' },
  { code: 'dataset_completeness_unknown', label: 'Completitud sin verificar', scope: 'dataset',
    description: 'Señala conjuntos que aún no tienen evidencia de completitud.' },
  { code: 'dataset_rejected_records', label: 'Registros rechazados', scope: 'dataset',
    description: 'Hace visible que algunas filas no llegaron al conjunto canónico.' },
  { code: 'lineage_invalidated', label: 'Linaje invalidado', scope: 'dataset',
    description: 'Detecta rutas a evidencia que dejaron de cumplir el contrato.' },
  { code: 'duplicate_fingerprint', label: 'Huella repetida', scope: 'movement',
    description: 'Encuentra rasgos exactos repetidos sin afirmar que sean el mismo hecho.' },
  { code: 'reference_amount_conflict', label: 'Referencia contradictoria', scope: 'movement',
    description: 'Encuentra una referencia normalizada asociada a atributos distintos.' },
  { code: 'posting_delay_over_31_days', label: 'Registro tardío', scope: 'movement',
    description: 'Señala más de 31 días entre ocurrencia y contabilización.' },
  { code: 'amount_outlier_10x_median', label: 'Volumen fuera del patrón', scope: 'movement',
    description: 'Compara con diez veces la mediana exacta de una muestra suficiente.' },
  { code: 'cross_dataset_duplicate_fingerprint', label: 'Huella en varios conjuntos', scope: 'movement',
    description: 'Detecta una misma huella canónica en más de una publicación reciente.' },
  { code: 'reference_reuse_high_frequency', label: 'Referencia muy reutilizada', scope: 'movement',
    description: 'Señala una referencia repetida cinco o más veces dentro del conjunto.' },
  { code: 'same_day_same_amount_burst', label: 'Ráfaga de valores iguales', scope: 'movement',
    description: 'Agrupa cuatro o más movimientos distintos con el mismo valor y fecha.' },
  { code: 'rapid_reversal_pair', label: 'Reversión cercana', scope: 'movement',
    description: 'Encuentra entradas y salidas opuestas con referencia y valor coincidentes.' },
  { code: 'multiple_risk_indicators', label: 'Indicadores convergentes', scope: 'movement',
    description: 'Eleva prioridad únicamente cuando coinciden dos o más señales independientes.' },
] as const;

export type DeliveryState =
  'queued' | 'sending' | 'sent' | 'delivered' | 'failed' | 'uncertain' | 'suppressed';

export const DELIVERY_LABELS: Readonly<Record<DeliveryState, string>> = {
  queued: 'En cola',
  sending: 'En proceso',
  sent: 'Enviado al proveedor',
  delivered: 'Entregado',
  failed: 'Fallido',
  uncertain: 'Resultado por verificar',
  suppressed: 'Suprimido',
};

export const SUPPRESSION_LABELS: Readonly<Record<string, string>> = {
  adapter_unconfigured: 'Proveedor de correo sin configurar',
  user_opt_out: 'Preferencia de correo desactivada',
  quiet_hours: 'Dentro del horario de silencio',
  destination_unavailable: 'Destino no disponible',
  hard_bounce: 'El proveedor rechazó permanentemente el destino',
  provider_complaint: 'Destino suprimido por reporte del destinatario',
};

export function summarizeDeliveries(
  deliveries: readonly { status: DeliveryState }[],
): Record<DeliveryState, number> {
  const summary: Record<DeliveryState, number> = {
    queued: 0, sending: 0, sent: 0, delivered: 0, failed: 0,
    uncertain: 0, suppressed: 0,
  };
  for (const delivery of deliveries) summary[delivery.status] += 1;
  return summary;
}

export function formatBytes(value: number): string {
  if (!Number.isFinite(value) || value < 0) return '—';
  if (value < 1024) return `${value.toLocaleString('es-CO')} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toLocaleString('es-CO', {
    maximumFractionDigits: 1,
  })} KB`;
  if (value < 1024 ** 3) return `${(value / 1024 ** 2).toLocaleString('es-CO', {
    maximumFractionDigits: 1,
  })} MB`;
  return `${(value / 1024 ** 3).toLocaleString('es-CO', {
    maximumFractionDigits: 1,
  })} GB`;
}

export function formatLimit(value: number | null, unit: string): string {
  return value === null ? 'Sin límite publicado' : `${value.toLocaleString('es-CO')} ${unit}`;
}

export function formatMinorAmount(amount: number, currency: string): string {
  if (!Number.isSafeInteger(amount) || amount < 0 || !/^[A-Z]{3}$/.test(currency)) return '—';
  const formatter = new Intl.NumberFormat('es-CO', { style: 'currency', currency });
  const digits = formatter.resolvedOptions().maximumFractionDigits ?? 2;
  return formatter.format(amount / (10 ** digits));
}

export function usagePercent(value: number, limit: number | null): number | null {
  if (limit === null || limit <= 0 || !Number.isFinite(value) || value < 0) return null;
  return Math.min(100, Math.round((value / limit) * 100));
}

export function formatWebMoment(value: string): string {
  return new Intl.DateTimeFormat('es-CO', {
    dateStyle: 'medium', timeStyle: 'short', timeZone: 'America/Bogota',
  }).format(new Date(value));
}

export type FlowMetric<T> =
  | { state: 'available'; value: T }
  | { state: 'restricted' }
  | { state: 'unavailable' };

export type AccountingFacts = {
  accounts: FlowMetric<number>;
  sources: FlowMetric<number>;
  documents: FlowMetric<{ total: number; raw: number; quarantine: number }>;
  datasets: FlowMetric<{
    total: number;
    staging: number;
    validated: number;
    published: number;
  }>;
  balances: FlowMetric<{
    observations: number;
    statements: number;
    balanced: number;
  }>;
  close: FlowMetric<{ reviewReady: number; blocked: number }>;
  reports: FlowMetric<true>;
};

export type AccountingStageStatus =
  | 'done'
  | 'ready'
  | 'attention'
  | 'blocked'
  | 'restricted'
  | 'unavailable';

export type AccountingStage = {
  key: string;
  number: number;
  eyebrow: string;
  title: string;
  description: string;
  status: AccountingStageStatus;
  detail: string;
  href: string;
  action: string;
  boundary?: string;
};

function unavailableFrom(metrics: FlowMetric<unknown>[]): AccountingStageStatus | null {
  if (metrics.some((metric) => metric.state === 'unavailable')) return 'unavailable';
  if (metrics.some((metric) => metric.state === 'restricted')) return 'restricted';
  return null;
}

export function deriveAccountingFlow(
  companyId: string,
  facts: AccountingFacts,
): AccountingStage[] {
  const encoded = encodeURIComponent(companyId);
  const setupAccess = unavailableFrom([facts.accounts, facts.sources]);
  const accounts = facts.accounts.state === 'available' ? facts.accounts.value : 0;
  const sources = facts.sources.state === 'available' ? facts.sources.value : 0;
  const setupDone = accounts > 0 && sources > 0;

  const documents = facts.documents.state === 'available'
    ? facts.documents.value
    : { total: 0, raw: 0, quarantine: 0 };
  const datasets = facts.datasets.state === 'available'
    ? facts.datasets.value
    : { total: 0, staging: 0, validated: 0, published: 0 };
  const balances = facts.balances.state === 'available'
    ? facts.balances.value
    : { observations: 0, statements: 0, balanced: 0 };
  const close = facts.close.state === 'available'
    ? facts.close.value
    : { reviewReady: 0, blocked: 0 };

  return [
    {
      key: 'setup', number: 1, eyebrow: 'Base operativa',
      title: 'Configurar cuentas y fuentes',
      description: 'Define de dónde llega la evidencia y contra qué cuenta se publica.',
      status: setupAccess ?? (setupDone ? 'done' : 'blocked'),
      detail: setupAccess
        ? 'Tu rol no puede verificar esta configuración.'
        : `${accounts} cuenta(s) activa(s) · ${sources} fuente(s) activa(s)`,
      href: `/empresas/${encoded}/fuentes`, action: setupDone ? 'Revisar configuración' : 'Configurar origen',
    },
    {
      key: 'ingestion', number: 2, eyebrow: 'Evidencia',
      title: 'Recibir e inspeccionar documentos',
      description: 'Todo archivo entra en cuarentena y solo avanza después de una inspección completa.',
      status: facts.documents.state !== 'available'
        ? facts.documents.state
        : documents.raw > 0
          ? (documents.quarantine > 0 ? 'attention' : 'done')
          : documents.quarantine > 0 ? 'attention' : 'blocked',
      detail: facts.documents.state === 'available'
        ? `${documents.raw} inspeccionado(s) · ${documents.quarantine} en cuarentena`
        : 'No se puede determinar el estado de los documentos.',
      href: `/empresas/${encoded}/documentos`, action: documents.total > 0 ? 'Abrir documentos' : 'Cargar documento',
    },
    {
      key: 'canonical', number: 3, eyebrow: 'Preparación',
      title: 'Limpiar, mapear y publicar',
      description: 'Convierte una extracción en movimientos tipados, versionados y trazables.',
      status: facts.datasets.state !== 'available'
        ? facts.datasets.state
        : datasets.published > 0 ? 'done'
          : datasets.validated > 0 ? 'ready'
            : datasets.staging > 0 ? 'attention' : 'blocked',
      detail: facts.datasets.state === 'available'
        ? `${datasets.published} publicado(s) · ${datasets.validated} por revisar · ${datasets.staging} parcial(es)`
        : 'No se puede determinar el estado canónico.',
      href: `/empresas/${encoded}/documentos`, action: datasets.total > 0 ? 'Continuar preparación' : 'Elegir evidencia',
      boundary: 'Una versión parcial o no verificada nunca alimenta cierre certificado.',
    },
    {
      key: 'matching', number: 4, eyebrow: 'Conciliación',
      title: 'Cruzar movimientos y decidir',
      description: 'Compara versiones publicadas, explica candidatos y conserva la decisión humana.',
      status: facts.datasets.state !== 'available'
        ? facts.datasets.state
        : datasets.published >= 2 ? 'ready' : 'blocked',
      detail: datasets.published >= 2
        ? `${datasets.published} datasets publicados disponibles para comparar.`
        : 'Se necesitan dos datasets publicados de cuentas distintas.',
      href: `/empresas/${encoded}/conciliacion`, action: 'Abrir conciliación visual',
      boundary: 'Confirmar un candidato no modifica movimientos ni certifica saldos.',
    },
    {
      key: 'balances', number: 5, eyebrow: 'Control',
      title: 'Observar y conciliar saldos',
      description: 'Relaciona saldos de extracto y libros con partidas conciliatorias confirmadas.',
      status: facts.balances.state !== 'available'
        ? facts.balances.state
        : balances.balanced > 0 ? 'done'
          : balances.observations > 0 || balances.statements > 0 ? 'ready' : 'blocked',
      detail: facts.balances.state === 'available'
        ? `${balances.observations} observación(es) · ${balances.statements} estado(s) · ${balances.balanced} balanceado(s)`
        : 'No se puede determinar el estado de saldos.',
      href: `/empresas/${encoded}/conciliacion-saldos`, action: 'Abrir estación de saldos',
    },
    {
      key: 'close', number: 6, eyebrow: 'Segregación',
      title: 'Preparar expediente de cierre',
      description: 'Consolida completitud, saldos, linaje, excepciones y revisión independiente.',
      status: facts.close.state !== 'available'
        ? facts.close.state
        : close.reviewReady > 0 ? 'ready'
          : close.blocked > 0 ? 'attention' : 'blocked',
      detail: facts.close.state === 'available'
        ? `${close.reviewReady} periodo(s) listo(s) para revisión · ${close.blocked} bloqueado(s)`
        : 'No se puede determinar la preparación del cierre.',
      href: `/preparacion-cierre?empresa=${encoded}`, action: 'Abrir preparación de cierre',
      boundary: 'Este recorrido prepara y revisa; no ejecuta ni certifica el cierre.',
    },
    {
      key: 'reports', number: 7, eyebrow: 'Lectura',
      title: 'Consultar históricos e informes',
      description: 'Revisa actividad, volúmenes y series operativas por empresa y periodo.',
      status: facts.reports.state === 'available' ? 'ready' : facts.reports.state,
      detail: facts.reports.state === 'available'
        ? 'El centro operativo está disponible para esta empresa.'
        : 'Tu rol no puede consultar informes de esta empresa.',
      href: `/informes?empresa=${encoded}`, action: 'Abrir informes',
      boundary: 'Los informes actuales son operativos y no constituyen estados financieros certificados.',
    },
  ];
}

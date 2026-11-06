/**
 * Logica pura del modo pyme (ADR-039, FNC-SMB-004). No decide permisos ni
 * estados financieros: traduce lo que la API ya resolvio a lenguaje llano y
 * agrupa lo pendiente. La API vuelve a exigir cada guarda.
 */

import type {
  AccountingPeriodClose,
  ArtifactSummary,
  BalanceReconciliationStatement,
  CandidateMovement,
  CandidateTolerance,
  DatasetSummary,
  MatchReview,
  OperatingProfile,
  ReconciliationCandidate,
  ReconciliationRule,
  ReconciliationSummary,
  ReconcilingItem,
  ReviewMode,
  RuleStatus,
  TeamSizeBand,
  TemplateDetection,
  UnmatchedMovement,
  UploadCadence,
  UploadSchedule,
} from './api';
import { reconciliationReviewUrl } from './reconciliation';

export const TEAM_SIZE_OPTIONS: ReadonlyArray<{
  band: TeamSizeBand;
  label: string;
  profile: OperatingProfile;
  hint: string;
}> = [
  {
    band: '1-2',
    label: '1–2 personas',
    profile: 'simple',
    hint: 'Simple: puedes conciliar y cerrar tú solo; tu contador puede certificar después.',
  },
  {
    band: '3+',
    label: '3 o más',
    profile: 'estricto',
    hint: 'Estricto: cada decisión la confirma otra persona.',
  },
];

export function parseTeamSizeBand(value: unknown): TeamSizeBand | null {
  return value === '1-2' || value === '3+' ? value : null;
}

export const PROFILE_LABELS: Record<OperatingProfile, string> = {
  simple: 'Simple',
  estricto: 'Estricto',
};

export const PROFILE_DESCRIPTIONS: Record<OperatingProfile, string> = {
  simple: 'Puedes conciliar y cerrar tú solo. Tus decisiones quedan marcadas como autorrevisadas y tu contador puede certificar el cierre después.',
  estricto: 'Cada decisión la confirma una persona distinta de quien la propuso.',
};

/** Ausente o desconocido equivale a `estricto`, el valor seguro. */
export function operatingProfileOf(
  company: { operating_profile?: string | null },
): OperatingProfile {
  return company.operating_profile === 'simple' ? 'simple' : 'estricto';
}

export function parseOperatingProfile(value: unknown): OperatingProfile | null {
  return value === 'simple' || value === 'estricto' ? value : null;
}

export const REVIEW_MODE_LABELS: Record<ReviewMode, string> = {
  independent: 'Revisado por otra persona',
  self_reviewed: 'Autorrevisado',
  approved_rule: 'Regla aprobada',
};

/** `null` cuando la API aun no informa el modo: no se inventa uno. */
export function reviewModeLabel(mode: string | null | undefined): string | null {
  return mode && mode in REVIEW_MODE_LABELS
    ? REVIEW_MODE_LABELS[mode as ReviewMode]
    : null;
}

export const PROFILE_REASON_MIN = 10;
export const PROFILE_REASON_MAX = 500;

export function validProfileReason(value: string): boolean {
  const reason = value.trim();
  return reason.length >= PROFILE_REASON_MIN && reason.length <= PROFILE_REASON_MAX
    && !Array.from(reason).some((char) => char.charCodeAt(0) < 32);
}

export type CloseCertificationView = {
  state: 'self_reviewed' | 'certified' | 'reopened';
  label: string;
};

/**
 * Estado legible del cierre. Una respuesta sin campos de certificacion es un
 * cierre anterior a ADR-039, que nacio con revision independiente.
 */
export function closeCertificationView(close: AccountingPeriodClose): CloseCertificationView {
  if (close.status === 'reopened') {
    return { state: 'reopened', label: 'Periodo reabierto' };
  }
  const record = close.certification_record ?? null;
  if (record) {
    return {
      state: 'certified',
      label: `Cerrado — certificado por ${record.certifier_name}`,
    };
  }
  if (close.certification === 'self_reviewed') {
    return { state: 'self_reviewed', label: 'Cerrado — autorrevisado' };
  }
  return { state: 'certified', label: 'Cerrado — certificado por otra persona' };
}

/**
 * Pista de interfaz para mostrar el boton de certificar. La API decide: exige
 * revisor elegible, que no haya preparado ni cerrado y un cierre vigente.
 */
export function mayOfferCertification(
  close: AccountingPeriodClose,
  actorId: string,
  permissions: readonly string[],
): boolean {
  return close.certification === 'self_reviewed'
    && !close.certification_record
    && close.status !== 'reopened'
    && close.closed_by !== actorId
    && permissions.includes('close.approve');
}

/** Cierre mas reciente que no fue reabierto, si existe. */
export function latestClose(
  closes: readonly AccountingPeriodClose[],
): AccountingPeriodClose | null {
  const sorted = [...closes].sort((left, right) =>
    right.period_end.localeCompare(left.period_end)
    || right.version - left.version);
  return sorted.find((close) => close.status !== 'reopened') ?? sorted[0] ?? null;
}

export type PendingKind = 'candidate' | 'dataset' | 'item' | 'difference';

export type PendingEntry = {
  key: string;
  kind: PendingKind;
  title: string;
  detail: string;
  explanation: string[];
  reviewMode: string | null;
  href: string;
};

export type PendingSources = {
  reviews: readonly MatchReview[] | null;
  datasets: readonly DatasetSummary[] | null;
  items: readonly ReconcilingItem[] | null;
  statements: readonly BalanceReconciliationStatement[] | null;
};

const SIGNAL_TEXT: Record<string, string> = {
  exact_amount: 'El monto coincide exactamente.',
  same_currency: 'La moneda es la misma.',
  opposite_direction: 'Uno es entrada y el otro salida.',
  different_financial_account: 'Vienen de cuentas distintas.',
  date_within_explicit_window: 'Las fechas están dentro de la ventana permitida.',
  same_normalised_reference: 'La referencia coincide.',
};

/** Usa la explicacion de la API; sin ella, describe las senales conocidas. */
export function candidateExplanation(review: MatchReview): string[] {
  const provided = (review.explanation ?? []).filter(
    (line): line is string => typeof line === 'string' && line.trim() !== '');
  if (provided.length) return provided;
  return review.signals.map((signal) => SIGNAL_TEXT[signal] ?? signal);
}

function latestStatements(
  statements: readonly BalanceReconciliationStatement[],
): BalanceReconciliationStatement[] {
  const byRoot = new Map<string, BalanceReconciliationStatement>();
  for (const statement of statements) {
    const seen = byRoot.get(statement.statement_root_id);
    if (!seen || statement.version > seen.version) {
      byRoot.set(statement.statement_root_id, statement);
    }
  }
  return [...byRoot.values()];
}

/**
 * Bandeja unica: solo lo que no cuadra o espera una decision. Nunca suma
 * importes ni concluye que algo esta conciliado.
 */
export function buildPendingInbox(companyId: string, sources: PendingSources): PendingEntry[] {
  const company = encodeURIComponent(companyId);
  const entries: PendingEntry[] = [];

  for (const review of sources.reviews ?? []) {
    if (review.status !== 'open') continue;
    entries.push({
      key: `candidate:${review.candidate_id}`,
      kind: 'candidate',
      title: review.confirmation_conflict
        ? 'Posible cruce en conflicto'
        : 'Posible cruce por confirmar',
      detail: `Propuesto por ${review.proposed_by_name} · ${review.date_distance_days} día(s) de diferencia`,
      explanation: candidateExplanation(review),
      reviewMode: review.review_mode ?? null,
      href: reconciliationReviewUrl(companyId, {
        leftDatasetId: review.left_dataset_id,
        rightDatasetId: review.right_dataset_id,
        maxDays: review.date_window_days,
        referenceMode: 'all',
        page: 0,
      }, review.candidate_id),
    });
  }

  for (const dataset of sources.datasets ?? []) {
    if (dataset.state !== 'staging' && dataset.state !== 'validated') continue;
    entries.push({
      key: `dataset:${dataset.dataset_version_id}`,
      kind: 'dataset',
      title: dataset.state === 'validated'
        ? 'Archivo listo para revisar y publicar'
        : 'Archivo con datos por completar',
      detail: `${dataset.movement_count} movimiento(s) · ${dataset.rejected_count} rechazado(s)`,
      explanation: [],
      reviewMode: null,
      href: `/empresas/${company}/documentos/${encodeURIComponent(dataset.artifact_id)}`,
    });
  }

  for (const item of sources.items ?? []) {
    if (item.state !== 'proposed') continue;
    entries.push({
      key: `item:${item.item_decision_id}`,
      kind: 'item',
      title: 'Partida por explicar',
      detail: `${item.amount} ${item.currency_code} · ${item.adjustment_side === 'add_to_bank' ? 'suma a banco' : 'resta de banco'}`,
      explanation: [],
      reviewMode: item.review_mode ?? null,
      href: `/empresas/${company}/conciliacion-saldos`,
    });
  }

  for (const statement of latestStatements(sources.statements ?? [])) {
    if (statement.state !== 'draft' && statement.state !== 'review_required') continue;
    entries.push({
      key: `difference:${statement.statement_id}`,
      kind: 'difference',
      title: `Saldo sin cuadrar en ${statement.account_name}`,
      detail: `Diferencia sin explicar: ${statement.unexplained_difference} ${statement.currency_code}`,
      explanation: [],
      reviewMode: null,
      href: `/empresas/${company}/conciliacion-saldos`,
    });
  }

  return entries;
}

// --------------------------------------------------------------------------- //
// Bandeja «Revisar pendientes», reglas, plantillas y cadencia (FNC-SMB-003..006)
// --------------------------------------------------------------------------- //

/**
 * Tolerancia por defecto del modo simple para buscar candidatos con diferencia
 * (retenciones, comisiones, GMF). HIPOTESIS A CALIBRAR: estos valores no salen
 * de datos reales; se revisan con el corpus autorizado despues de DRG-00. Solo
 * amplian candidatos: la diferencia se muestra y una persona decide. La API los
 * vuelve a acotar (maximo 5 % y 10.000.000) y nunca usa float.
 */
export const SIMPLE_CANDIDATE_TOLERANCE: CandidateTolerance = {
  percent: '5',
  amount: '20000',
};

/** Ventana de fechas de la bandeja simple; la misma que usa el explorador. */
export const SIMPLE_MAX_DAYS = 3;

export type SimplePair = { leftDatasetId: string; rightDatasetId: string };

/**
 * El par que la bandeja compara: el archivo publicado mas reciente y el mas
 * reciente de otra fuente. Sin dos fuentes publicadas no hay par que proponer.
 */
export function selectSimplePair(
  datasets: readonly DatasetSummary[],
  documents: readonly ArtifactSummary[],
): SimplePair | null {
  const sourceOf = new Map(documents.map((item) => [item.artifact_id, item.data_source_id]));
  const published = datasets
    .filter((item) => item.state === 'published')
    .sort((left, right) =>
      (right.published_at ?? right.prepared_at).localeCompare(left.published_at ?? left.prepared_at)
      || right.dataset_version_id.localeCompare(left.dataset_version_id));
  const first = published[0];
  if (!first) return null;
  const firstSource = sourceOf.get(first.artifact_id) ?? null;
  const second = published.find((item) => item !== first
    && (sourceOf.get(item.artifact_id) ?? null) !== firstSource);
  if (!second) return null;
  return { leftDatasetId: first.dataset_version_id, rightDatasetId: second.dataset_version_id };
}

function pairKey(left: string, right: string): string {
  return [left, right].sort().join(':');
}

export type SimpleSuggestion = {
  key: string;
  leftMovementId: string;
  rightMovementId: string;
  title: string;
  detail: string;
  explanation: string[];
  amountDifference: string | null;
};

function movementLine(movement: CandidateMovement): string {
  return `${movement.occurred_on} · ${movement.description} · ${movement.amount} ${movement.currency}`;
}

/**
 * Sugerencias del explorador que la persona puede confirmar o rechazar. Solo
 * pares cuyos dos movimientos siguen sin cruzar y que aun no tienen expediente
 * abierto (esos ya aparecen como candidatos abiertos).
 */
export function buildSuggestions(
  candidates: readonly ReconciliationCandidate[],
  unmatched: readonly UnmatchedMovement[],
  openReviews: readonly MatchReview[],
): SimpleSuggestion[] {
  const free = new Set(unmatched.map((item) => item.movement_id));
  const reviewed = new Set(openReviews.map((item) =>
    pairKey(item.left_movement_id, item.right_movement_id)));
  const seen = new Set<string>();
  const suggestions: SimpleSuggestion[] = [];
  for (const candidate of candidates) {
    const key = pairKey(candidate.left.movement_id, candidate.right.movement_id);
    if (seen.has(key) || reviewed.has(key)) continue;
    if (!free.has(candidate.left.movement_id) || !free.has(candidate.right.movement_id)) {
      continue;
    }
    seen.add(key);
    suggestions.push({
      key: `suggestion:${key}`,
      leftMovementId: candidate.left.movement_id,
      rightMovementId: candidate.right.movement_id,
      title: candidate.amount_difference ? 'Posible cruce con diferencia' : 'Posible cruce',
      detail: `${movementLine(candidate.left)} ↔ ${movementLine(candidate.right)}`,
      explanation: candidate.explanation?.length
        ? candidate.explanation
        : candidate.signals.map((signal) => SIGNAL_TEXT[signal] ?? signal),
      amountDifference: candidate.amount_difference ?? null,
    });
  }
  return suggestions;
}

/** Movimientos sin cruce que no aparecen en ninguna sugerencia ni expediente. */
export function unpairedMovements(
  unmatched: readonly UnmatchedMovement[],
  suggestions: readonly SimpleSuggestion[],
): UnmatchedMovement[] {
  const suggested = new Set(suggestions.flatMap((item) =>
    [item.leftMovementId, item.rightMovementId]));
  return unmatched.filter((item) => !item.has_open_candidate && !suggested.has(item.movement_id));
}

/** Aplicaciones de regla vigentes: se pueden deshacer desde la bandeja. */
export function ruleApplications(reviews: readonly MatchReview[]): MatchReview[] {
  return reviews.filter((item) => item.status === 'confirmed'
    && item.decision?.review_mode === 'approved_rule'
    && !item.decision.reversal);
}

/** «N conciliados, M pendientes, K por revisar». Conteos, nunca importes. */
export function summaryLine(summary: ReconciliationSummary): string {
  return `${summary.matched} conciliados, ${summary.pending} pendientes, ${summary.to_review} por revisar`;
}

export const CADENCE_OPTIONS: ReadonlyArray<{ cadence: UploadCadence; label: string }> = [
  { cadence: 'weekly', label: 'Semanal' },
  { cadence: 'biweekly', label: 'Quincenal' },
  { cadence: 'monthly', label: 'Mensual' },
];

export function parseCadence(value: unknown): UploadCadence | null {
  return value === 'weekly' || value === 'biweekly' || value === 'monthly' ? value : null;
}

export function cadenceLabel(cadence: UploadCadence | null): string {
  return CADENCE_OPTIONS.find((option) => option.cadence === cadence)?.label ?? 'Sin definir';
}

/** Texto del recordatorio en la app. Nunca dice que se envio un correo. */
export function uploadReminderText(schedule: UploadSchedule): string {
  const period = schedule.current_period;
  if (!schedule.cadence || !period) {
    return 'Elige cada cuánto subes tu extracto y te lo recordamos aquí, dentro de Fincilia.';
  }
  if (period.reminder_state === 'received') {
    return `Ya recibimos archivos del periodo ${period.period_start} a ${period.period_end}.`;
  }
  if (period.reminder_state === 'due_soon') {
    return `Sube tu extracto antes del ${period.due_on}: aún no hay archivos de este periodo.`;
  }
  return `Próxima carga: antes del ${period.due_on}.`;
}

export type TemplateOffer =
  | { kind: 'template'; label: string; warning: string | null }
  | { kind: 'manual' }
  | { kind: 'pending' };

const STRUCTURED_LABELS: Record<string, string> = {
  'dian-ubl-invoice': 'factura electrónica DIAN',
  'swift-mt940': 'extracto MT940',
};

/**
 * Que ofrecer despues de procesar un documento. Una plantilla bancaria es una
 * hipotesis sintetica: se ofrece con aviso explicito. DIAN y MT940 tienen
 * estructura fijada por su norma y pasan sin aviso.
 */
export function templateOffer(detection: TemplateDetection | null): TemplateOffer {
  if (!detection || detection.status === 'not_extracted') return { kind: 'pending' };
  if (detection.status !== 'ready' || !detection.template) return { kind: 'manual' };
  const template = detection.template;
  const id = template.template_id ?? template.id ?? '';
  if (template.source === 'format_specification' || STRUCTURED_LABELS[id]) {
    return {
      kind: 'template',
      label: `Usar estructura de ${STRUCTURED_LABELS[id] ?? 'formato conocido'}`,
      warning: null,
    };
  }
  return {
    kind: 'template',
    label: `Usar plantilla ${template.bank ?? 'del banco'}`,
    warning: template.calibration === 'synthetic_hypothesis' || !template.calibration
      ? 'Plantilla de prueba — verifica las columnas'
      : null,
  };
}

export const RULE_STATUS_LABELS: Record<RuleStatus, string> = {
  proposed: 'Propuesta',
  active: 'Activa',
  paused: 'Pausada',
  retired: 'Retirada',
};

export type RuleAction = 'approve' | 'pause' | 'resume' | 'retire';

/**
 * Botones que la interfaz ofrece. Pista visual solamente: la API exige permiso,
 * perfil y estado. En `estricto` quien creo la regla no la aprueba.
 */
export function ruleActions(
  rule: ReconciliationRule,
  context: { actorId: string; permissions: readonly string[]; profile: OperatingProfile },
): RuleAction[] {
  if (!context.permissions.includes('match.confirm')) return [];
  if (rule.status === 'retired') return [];
  const actions: RuleAction[] = [];
  if (rule.status === 'proposed'
      && (context.profile === 'simple' || rule.created_by !== context.actorId)) {
    actions.push('approve');
  }
  if (rule.status === 'active') actions.push('pause');
  if (rule.status === 'paused') actions.push('resume');
  actions.push('retire');
  return actions;
}

/** Etiqueta honesta de la aprobacion: «Autorrevisada» si fue la misma persona. */
export function ruleApprovalLabel(rule: ReconciliationRule): string | null {
  if (!rule.approval) return null;
  return rule.approval.review_mode === 'self_reviewed'
    ? `Autorrevisada por ${rule.approval.approved_by_name}`
    : `Aprobada por ${rule.approval.approved_by_name}`;
}

const KEY_PATTERN = /^[A-Za-z0-9._:-]{16,128}$/;

/** Claves derivadas para los pasos de un mismo gesto (p. ej. crear y aprobar). */
export function derivedKey(base: string, step: string): string | null {
  const key = `${base}.${step}`;
  return KEY_PATTERN.test(key) ? key : null;
}

import { reviewModeLabel } from '@/lib/simple-mode';

/**
 * Muestra como se reviso una decision (ADR-039). Si la API aun no informa el
 * modo, no se muestra nada: nunca se presume una revision independiente.
 */
export function ReviewModeBadge({ mode }: { mode: string | null | undefined }) {
  const label = reviewModeLabel(mode);
  if (!label) return null;
  return (
    <span className={`tag review-mode review-mode--${mode}`}>
      {label}
    </span>
  );
}

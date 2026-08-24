'use client';

type RetryButtonProps = Readonly<{
  onRetry: () => void;
  label?: string;
}>;

export function RetryButton({
  onRetry,
  label = 'Intentar de nuevo',
}: RetryButtonProps) {
  return (
    <button type="button" onClick={onRetry}>
      {label}
    </button>
  );
}

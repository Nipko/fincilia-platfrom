'use client';

import { PageState } from '@/components/page-state';
import { RetryButton } from '@/components/retry-button';

type ErrorPageProps = Readonly<{
  error: Error & { digest?: string };
  reset: () => void;
}>;

export default function ErrorPage({ reset }: ErrorPageProps) {
  return (
    <PageState
      action={<RetryButton onRetry={reset} />}
      description="No pudimos completar la solicitud. Puedes volver a intentarlo."
      headingAs="h1"
      kind="degraded"
      title="Esta vista no está disponible"
    />
  );
}

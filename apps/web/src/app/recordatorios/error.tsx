'use client';

import { PageState } from '@/components/page-state';

export default function OperationsError({ reset }: { reset: () => void }) {
  return (
    <main>
      <PageState
        kind="degraded"
        headingAs="h1"
        title="No se pudo actualizar el centro operativo"
        description="Los periodos siguen conservados. Intenta consultar la proyeccion de nuevo."
        action={<button type="button" onClick={reset}>Reintentar</button>}
      />
    </main>
  );
}

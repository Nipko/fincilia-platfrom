import { PageState } from '@/components/page-state';

export default function LoadingOperations() {
  return (
    <main>
      <PageState
        kind="loading"
        headingAs="h1"
        title="Actualizando ciclos"
        description="Consultando cada empresa autorizada sin mezclar sus datos."
      />
    </main>
  );
}

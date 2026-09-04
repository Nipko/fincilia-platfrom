import { PageState } from '@/components/page-state';

export default function LoadingOperations() {
  return (
    <div className="route-loading-boundary">
      <PageState
        kind="loading"
        headingAs="h1"
        title="Actualizando ciclos"
        description="Consultando cada empresa autorizada sin mezclar sus datos."
      />
    </div>
  );
}

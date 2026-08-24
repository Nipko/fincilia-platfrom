import { PageState } from '@/components/page-state';

export default function Loading() {
  return (
    <PageState
      description="Estamos preparando esta vista."
      headingAs="h1"
      kind="loading"
      title="Cargando información"
    />
  );
}

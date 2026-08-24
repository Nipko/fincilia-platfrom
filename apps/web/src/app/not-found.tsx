import Link from 'next/link';

import { PageState } from '@/components/page-state';

export default function NotFound() {
  return (
    <PageState
      action={
        <Link className="page-state__link" href="/">
          Volver al inicio
        </Link>
      }
      description="La dirección no existe o ya no está disponible para esta sesión."
      headingAs="h1"
      kind="not-found"
      title="No encontramos esta página"
    />
  );
}

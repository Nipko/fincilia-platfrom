import { LegalDocument } from '@/components/legal-document';
import { COOKIE_SECTIONS } from '@/lib/legal-content';

export default function CookiesPage() {
  return <LegalDocument eyebrow="Centro legal" title="Aviso de cookies"
    summary="Cookies estrictamente necesarias para sesión, seguridad y OAuth."
    sections={COOKIE_SECTIONS} />;
}

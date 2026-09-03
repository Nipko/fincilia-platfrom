import { LegalDocument } from '@/components/legal-document';
import { COOKIE_SECTIONS } from '@/lib/legal-content';
import { LEGAL_DOCUMENTS } from '@/lib/legal-publication';

export default function CookiesPage() {
  return <LegalDocument eyebrow="Centro legal" title="Aviso de cookies"
    summary="Cookies estrictamente necesarias para sesión, seguridad y OAuth."
    {...LEGAL_DOCUMENTS.cookies}
    sections={COOKIE_SECTIONS} />;
}

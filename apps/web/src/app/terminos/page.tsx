import { LegalDocument } from '@/components/legal-document';
import { TERMS_SECTIONS } from '@/lib/legal-content';

export default function TermsPage() {
  return <LegalDocument eyebrow="Centro legal" title="Términos de la beta cerrada"
    summary="Reglas para evaluar Fincilia de forma segura y exclusivamente sintética."
    sections={TERMS_SECTIONS} />;
}

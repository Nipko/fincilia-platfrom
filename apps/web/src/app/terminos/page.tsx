import { LegalDocument } from '@/components/legal-document';
import { TERMS_SECTIONS } from '@/lib/legal-content';
import { LEGAL_DOCUMENTS } from '@/lib/legal-publication';

export default function TermsPage() {
  return <LegalDocument eyebrow="Centro legal" title="Términos del servicio"
    summary="Reglas vigentes para usar Fincilia y participar en su entorno UAT."
    {...LEGAL_DOCUMENTS.terms}
    sections={TERMS_SECTIONS} />;
}

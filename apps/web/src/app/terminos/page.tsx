import { LegalDocument } from '@/components/legal-document';
import { TERMS_SECTIONS } from '@/lib/legal-content';

export default function TermsPage() {
  return <LegalDocument eyebrow="Centro legal" title="Términos del servicio"
    summary="Reglas vigentes para usar Fincilia de forma segura durante preproducción."
    sections={TERMS_SECTIONS} />;
}

import { LegalDocument } from '@/components/legal-document';
import { SECURITY_SECTIONS } from '@/lib/legal-content';
import { LEGAL_DOCUMENTS } from '@/lib/legal-publication';

export default function SecurityPage() {
  return <LegalDocument eyebrow="Confianza" title="Seguridad en Fincilia"
    summary="Controles actuales, responsabilidad compartida y reporte responsable."
    {...LEGAL_DOCUMENTS.security}
    sections={SECURITY_SECTIONS} />;
}

import { LegalDocument } from '@/components/legal-document';
import { SECURITY_SECTIONS } from '@/lib/legal-content';

export default function SecurityPage() {
  return <LegalDocument eyebrow="Confianza" title="Seguridad en Fincilia"
    summary="Controles actuales, límites de la beta y reporte responsable."
    sections={SECURITY_SECTIONS} />;
}

import { LegalDocument } from '@/components/legal-document';
import { SUBPROCESSOR_SECTIONS } from '@/lib/legal-content';

export default function SubprocessorsPage() {
  return <LegalDocument eyebrow="Centro legal" title="Subencargados y proveedores"
    summary="Servicios previstos, ubicación y controles antes de procesar datos reales."
    sections={SUBPROCESSOR_SECTIONS} />;
}

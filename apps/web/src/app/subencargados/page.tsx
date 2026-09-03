import { LegalDocument } from '@/components/legal-document';
import { SUBPROCESSOR_SECTIONS } from '@/lib/legal-content';
import { LEGAL_DOCUMENTS } from '@/lib/legal-publication';

export default function SubprocessorsPage() {
  return <LegalDocument eyebrow="Centro legal" title="Subencargados y proveedores"
    summary="Proveedores, funciones, ubicaciones y límites aplicables al servicio."
    {...LEGAL_DOCUMENTS.subprocessors}
    sections={SUBPROCESSOR_SECTIONS} />;
}

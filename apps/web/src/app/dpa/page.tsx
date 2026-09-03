import { LegalDocument } from '@/components/legal-document';
import { DPA_SECTIONS } from '@/lib/legal-content';
import { LEGAL_DOCUMENTS } from '@/lib/legal-publication';

export default function DpaPage() {
  return <LegalDocument eyebrow="Centro legal" title="Acuerdo de tratamiento (DPA)"
    summary="Modelo contractual para organizaciones que encarguen tratamiento a Fincilia."
    {...LEGAL_DOCUMENTS.dpa}
    sections={DPA_SECTIONS} />;
}

import { LegalDocument } from '@/components/legal-document';
import { DPA_SECTIONS } from '@/lib/legal-content';

export default function DpaPage() {
  return <LegalDocument eyebrow="Centro legal" title="Acuerdo de tratamiento (DPA)"
    summary="Estructura prevista para acordar el tratamiento antes de cualquier dato real."
    sections={DPA_SECTIONS} />;
}

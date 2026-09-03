import { LegalDocument } from '@/components/legal-document';
import { SUBPROCESSOR_SECTIONS } from '@/lib/legal-content';
import { LEGAL_DOCUMENTS } from '@/lib/legal-publication';

export const metadata = {
  title: 'Subprocessors | Fincilia',
  description: 'Service providers, functions, locations, and limits applicable to Fincilia.',
};

export default function SubprocessorsPage() {
  return <LegalDocument eyebrow="Legal center" title="Subprocessors and providers"
    summary="Service providers, functions, locations, and limits applicable to Fincilia."
    {...LEGAL_DOCUMENTS.subprocessors}
    sections={SUBPROCESSOR_SECTIONS} />;
}

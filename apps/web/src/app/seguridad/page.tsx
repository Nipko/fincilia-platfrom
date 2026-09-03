import { LegalDocument } from '@/components/legal-document';
import { SECURITY_SECTIONS } from '@/lib/legal-content';
import { LEGAL_DOCUMENTS } from '@/lib/legal-publication';

export const metadata = {
  title: 'Security | Fincilia',
  description: 'Fincilia security controls, shared responsibility, and responsible reporting.',
};

export default function SecurityPage() {
  return <LegalDocument eyebrow="Trust center" title="Security at Fincilia"
    summary="Current controls, shared responsibility, and responsible reporting."
    {...LEGAL_DOCUMENTS.security}
    sections={SECURITY_SECTIONS} />;
}

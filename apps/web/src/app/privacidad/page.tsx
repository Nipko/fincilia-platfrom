import { LegalDocument } from '@/components/legal-document';
import { PRIVACY_SECTIONS } from '@/lib/legal-content';
import { LEGAL_DOCUMENTS } from '@/lib/legal-publication';

export const metadata = {
  title: 'Privacy Policy | Fincilia',
  description: 'How Fincilia accesses, uses, protects, retains, and deletes information.',
};

export default function PrivacyPage() {
  return <LegalDocument eyebrow="Legal center" title="Privacy Policy"
    summary="How Fincilia accesses, uses, protects, retains, and deletes information."
    {...LEGAL_DOCUMENTS.privacy}
    sections={PRIVACY_SECTIONS} />;
}

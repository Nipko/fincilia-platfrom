import { LegalDocument } from '@/components/legal-document';
import { DELETION_SECTIONS } from '@/lib/legal-content';
import { LEGAL_DOCUMENTS } from '@/lib/legal-publication';

export const metadata = {
  title: 'Account and Data Deletion | Fincilia',
  description: 'How to request deletion and how Fincilia reconciles it with audit records and backups.',
};

export default function DeleteAccountPage() {
  return <LegalDocument eyebrow="Privacy" title="Account and Data Deletion"
    summary="How to request deletion and how Fincilia reconciles it with audit records and backups."
    {...LEGAL_DOCUMENTS.deletion}
    sections={DELETION_SECTIONS} />;
}

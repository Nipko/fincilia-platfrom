import { LegalDocument } from '@/components/legal-document';
import { DELETION_SECTIONS } from '@/lib/legal-content';
import { LEGAL_DOCUMENTS } from '@/lib/legal-publication';

export default function DeleteAccountPage() {
  return <LegalDocument eyebrow="Privacidad" title="Eliminación de cuenta y datos"
    summary="Cómo solicitar eliminación y cómo se reconcilia con auditoría y backups."
    {...LEGAL_DOCUMENTS.deletion}
    sections={DELETION_SECTIONS} />;
}

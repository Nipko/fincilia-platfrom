import { LegalDocument } from '@/components/legal-document';
import { DELETION_SECTIONS } from '@/lib/legal-content';

export default function DeleteAccountPage() {
  return <LegalDocument eyebrow="Privacidad" title="Eliminación de cuenta y datos"
    summary="Cómo solicitar eliminación y cómo se reconcilia con auditoría y backups."
    sections={DELETION_SECTIONS} />;
}

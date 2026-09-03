import { LegalDocument } from '@/components/legal-document';
import { PRIVACY_SECTIONS } from '@/lib/legal-content';
import { LEGAL_DOCUMENTS } from '@/lib/legal-publication';

export default function PrivacyPage() {
  return <LegalDocument eyebrow="Centro legal" title="Política de privacidad"
    summary="Cómo Fincilia accede, usa, protege, conserva y elimina información."
    {...LEGAL_DOCUMENTS.privacy}
    sections={PRIVACY_SECTIONS} />;
}

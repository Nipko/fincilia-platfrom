import { LegalDocument } from '@/components/legal-document';
import { PRIVACY_SECTIONS } from '@/lib/legal-content';

export default function PrivacyPage() {
  return <LegalDocument eyebrow="Centro legal" title="Política de privacidad"
    summary="Cómo Fincilia accede, usa, protege, conserva y elimina información."
    sections={PRIVACY_SECTIONS} />;
}

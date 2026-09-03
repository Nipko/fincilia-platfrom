import { LegalDocument } from '@/components/legal-document';
import { COOKIE_SECTIONS } from '@/lib/legal-content';
import { LEGAL_DOCUMENTS } from '@/lib/legal-publication';

export const metadata = {
  title: 'Cookie Notice | Fincilia',
  description: 'Strictly necessary cookies used for session security and OAuth.',
  alternates: { canonical: 'https://fincilia.com/cookies' },
};

export default function CookiesPage() {
  return <LegalDocument eyebrow="Legal center" title="Cookie Notice"
    summary="Strictly necessary cookies used for session security and OAuth."
    {...LEGAL_DOCUMENTS.cookies}
    sections={COOKIE_SECTIONS} />;
}

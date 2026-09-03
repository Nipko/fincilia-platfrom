import { LegalDocument } from '@/components/legal-document';
import { TERMS_SECTIONS } from '@/lib/legal-content';
import { LEGAL_DOCUMENTS } from '@/lib/legal-publication';

export const metadata = {
  title: 'Terms of Service | Fincilia',
  description: 'The terms that govern use of Fincilia and its UAT environment.',
  alternates: { canonical: 'https://fincilia.com/terms' },
};

export default function TermsPage() {
  return <LegalDocument eyebrow="Legal center" title="Terms of Service"
    summary="The terms that govern use of Fincilia and its UAT environment."
    {...LEGAL_DOCUMENTS.terms}
    sections={TERMS_SECTIONS} />;
}

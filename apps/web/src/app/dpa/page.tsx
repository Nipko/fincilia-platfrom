import { LegalDocument } from '@/components/legal-document';
import { DPA_SECTIONS } from '@/lib/legal-content';
import { LEGAL_DOCUMENTS } from '@/lib/legal-publication';

export const metadata = {
  title: 'Data Processing Agreement | Fincilia',
  description: 'Contract model for organizations that engage Fincilia to process data.',
  alternates: { canonical: 'https://fincilia.com/dpa' },
};

export default function DpaPage() {
  return <LegalDocument eyebrow="Legal center" title="Data Processing Agreement (DPA)"
    summary="Contract model for organizations that engage Fincilia to process data."
    {...LEGAL_DOCUMENTS.dpa}
    sections={DPA_SECTIONS} />;
}

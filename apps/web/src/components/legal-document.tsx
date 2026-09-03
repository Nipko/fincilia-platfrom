import Link from 'next/link';

export type LegalSection = {
  title: string;
  paragraphs?: readonly string[];
  bullets?: readonly string[];
};

type LegalDocumentProps = {
  eyebrow: string;
  title: string;
  summary: string;
  sections: readonly LegalSection[];
  version: string;
  effectiveDate: string;
  status: string;
};

export function LegalDocument({
  eyebrow,
  title,
  summary,
  sections,
  version,
  effectiveDate,
  status,
}: LegalDocumentProps) {
  return (
    <main className="legal-page" lang="en">
      <header className="legal-hero">
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="legal-hero__summary">{summary}</p>
        <div className="legal-status" role="note">
          <strong>{status}</strong>
          <span>Version {version} · effective {effectiveDate}</span>
        </div>
      </header>

      <div className="legal-layout">
        <nav aria-label="On this page" className="legal-toc card">
          <strong>On this page</strong>
          {sections.map((section, index) => (
            <a href={`#seccion-${index + 1}`} key={section.title}>{section.title}</a>
          ))}
        </nav>

        <article className="legal-document card">
          {sections.map((section, index) => (
            <section id={`seccion-${index + 1}`} key={section.title}>
              <h2>{section.title}</h2>
              {section.paragraphs?.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
              {section.bullets ? (
                <ul>
                  {section.bullets.map((bullet) => <li key={bullet}>{bullet}</li>)}
                </ul>
              ) : null}
            </section>
          ))}
          <aside className="legal-review-note">
            To request a copy of this version, an accessible format, or information
            about an earlier version, email legal@fincilia.com. Organization-specific
            terms may supplement this document without reducing mandatory rights.
          </aside>
        </article>
      </div>

      <nav aria-label="Related legal documents" className="legal-related">
        <Link href="/privacy">Privacy</Link>
        <Link href="/terms">Terms</Link>
        <Link href="/cookies">Cookies</Link>
        <Link href="/security">Security</Link>
        <Link href="/dpa">DPA</Link>
        <Link href="/subprocessors">Subprocessors</Link>
        <Link href="/delete-account">Delete account</Link>
      </nav>
    </main>
  );
}

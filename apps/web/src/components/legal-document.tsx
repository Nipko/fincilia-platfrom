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
    <main className="legal-page">
      <header className="legal-hero">
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="legal-hero__summary">{summary}</p>
        <div className="legal-status" role="note">
          <strong>{status}</strong>
          <span>Versión {version} · vigente desde el {effectiveDate}</span>
        </div>
      </header>

      <div className="legal-layout">
        <nav aria-label="En esta página" className="legal-toc card">
          <strong>En esta página</strong>
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
            Si necesitas una copia de esta versión, un formato accesible o información
            sobre una versión anterior, escribe a legal@fincilia.com. Las condiciones
            contractuales específicas de una organización pueden complementar este
            documento sin reducir derechos obligatorios.
          </aside>
        </article>
      </div>

      <nav aria-label="Documentos legales relacionados" className="legal-related">
        <Link href="/privacidad">Privacidad</Link>
        <Link href="/terminos">Términos</Link>
        <Link href="/cookies">Cookies</Link>
        <Link href="/seguridad">Seguridad</Link>
        <Link href="/dpa">DPA</Link>
        <Link href="/subencargados">Subencargados</Link>
        <Link href="/eliminar-cuenta">Eliminar cuenta</Link>
      </nav>
    </main>
  );
}

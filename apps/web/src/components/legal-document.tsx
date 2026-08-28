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
};

export function LegalDocument({ eyebrow, title, summary, sections }: LegalDocumentProps) {
  return (
    <main className="legal-page">
      <header className="legal-hero">
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="legal-hero__summary">{summary}</p>
        <div className="legal-status" role="note">
          <strong>Borrador de preproducción</strong>
          <span>Versión 0.1 · 28 de agosto de 2026 · revisión jurídica pendiente</span>
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
            Estos textos documentan la postura actual del producto y no sustituyen
            asesoría legal. Antes de tratar datos reales deben completarse la razón
            social, domicilio, jurisdicción y aprobaciones nominales pendientes.
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

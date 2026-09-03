import { describe, expect, it } from 'vitest';

import {
  COOKIE_SECTIONS,
  DELETION_SECTIONS,
  PRIVACY_SECTIONS,
  SUBPROCESSOR_SECTIONS,
  TERMS_SECTIONS,
} from '../legal-content';
import {
  LEGAL_DOCUMENTS,
  PRIVACY_VERSION,
  TERMS_VERSION,
} from '../legal-publication';

function text(sections: readonly { paragraphs?: readonly string[]; bullets?: readonly string[] }[]) {
  return sections.flatMap((section) => [
    ...(section.paragraphs ?? []),
    ...(section.bullets ?? []),
  ]).join('\n');
}

describe('publicación legal de Fincilia', () => {
  it('identifica responsable, domicilio y canales atendidos', () => {
    const policy = text(PRIVACY_SECTIONS);

    expect(policy).toContain('Parallext LLC');
    expect(policy).toContain('7345 W Sand Lake Rd');
    expect(policy).toContain('+57 313 432 8491');
    expect(policy).toContain('privacy@fincilia.com');
    expect(policy).toContain('legal@fincilia.com');
    expect(policy).toContain('support@fincilia.com');
    expect(policy).not.toMatch(/se completar[aá]n|bases candidatas|revisi[oó]n jur[ií]dica pendiente/i);
  });

  it('declara el uso limitado de Google y scopes mínimos', () => {
    const policy = text(PRIVACY_SECTIONS);

    expect(policy).toContain('openid, email y profile');
    expect(policy).toContain('No solicitamos acceso a Gmail, Google Drive');
    expect(policy).toContain('requisitos de uso limitado');
    expect(policy).toContain('No los vendemos');
  });

  it('publica proveedores reales sin presentar al responsable como subencargado', () => {
    const providers = text(SUBPROCESSOR_SECTIONS);

    for (const provider of ['Amazon Web Services', 'Google LLC', 'Namecheap', 'Cloudflare']) {
      expect(providers).toContain(provider);
    }
    expect(providers).not.toContain('Parallext.com: desarrollo');
  });

  it('documenta cookies, derechos, eliminación y límites UAT', () => {
    expect(text(COOKIE_SECTIONS)).toContain('máximo de diez minutos');
    expect(text(DELETION_SECTIONS)).toContain('quince días hábiles');
    expect(text(PRIVACY_SECTIONS)).toContain('diez días hábiles');
    expect(text(TERMS_SECTIONS)).toContain('El UAT es gratuito');
    expect(text(TERMS_SECTIONS)).toContain('Estado de Florida');
  });

  it('alinea los identificadores visibles con el consentimiento', () => {
    expect(TERMS_VERSION).toBe('terms-2026-09-03');
    expect(PRIVACY_VERSION).toBe('privacy-2026-09-03');
    expect(LEGAL_DOCUMENTS.terms.version).toBe(TERMS_VERSION);
    expect(LEGAL_DOCUMENTS.privacy.version).toBe(PRIVACY_VERSION);
  });
});

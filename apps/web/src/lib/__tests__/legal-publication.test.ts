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

describe('Fincilia legal publication', () => {
  it('identifies the controller, address, and monitored channels', () => {
    const policy = text(PRIVACY_SECTIONS);

    expect(policy).toContain('Parallext LLC');
    expect(policy).toContain('7345 W Sand Lake Rd');
    expect(policy).toContain('+57 313 432 8491');
    expect(policy).toContain('privacy@fincilia.com');
    expect(policy).toContain('legal@fincilia.com');
    expect(policy).toContain('support@fincilia.com');
    expect(policy).not.toMatch(/to be completed|candidate basis|legal review pending/i);
  });

  it('discloses limited Google use and minimum scopes', () => {
    const policy = text(PRIVACY_SECTIONS);

    expect(policy).toContain('openid, email, and profile');
    expect(policy).toContain('We do not request access to Gmail, Google Drive');
    expect(policy).toContain('Limited Use requirements');
    expect(policy).toContain('We do not sell it');
  });

  it('publishes actual providers without listing the controller as a subprocessor', () => {
    const providers = text(SUBPROCESSOR_SECTIONS);

    for (const provider of ['Amazon Web Services', 'Google LLC', 'Namecheap', 'Cloudflare']) {
      expect(providers).toContain(provider);
    }
    expect(providers).not.toContain('Parallext.com: development');
  });

  it('documents cookies, rights, deletion, and UAT limits', () => {
    expect(text(COOKIE_SECTIONS)).toContain('no more than ten minutes');
    expect(text(DELETION_SECTIONS)).toContain('fifteen business days');
    expect(text(PRIVACY_SECTIONS)).toContain('ten business days');
    expect(text(TERMS_SECTIONS)).toContain('UAT is free');
    expect(text(TERMS_SECTIONS)).toContain('State of Florida');
  });

  it('aligns visible identifiers with stored consent', () => {
    expect(TERMS_VERSION).toBe('terms-2026-09-03-en');
    expect(PRIVACY_VERSION).toBe('privacy-2026-09-03-en');
    expect(LEGAL_DOCUMENTS.terms.version).toBe(TERMS_VERSION);
    expect(LEGAL_DOCUMENTS.privacy.version).toBe(PRIVACY_VERSION);
  });
});

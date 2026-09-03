export const LEGAL_EFFECTIVE_DATE = 'September 3, 2026';

export const TERMS_VERSION = 'terms-2026-09-03-en';
export const PRIVACY_VERSION = 'privacy-2026-09-03-en';

export const LEGAL_DOCUMENTS = {
  privacy: {
    version: PRIVACY_VERSION,
    effectiveDate: LEGAL_EFFECTIVE_DATE,
    status: 'Current policy',
  },
  terms: {
    version: TERMS_VERSION,
    effectiveDate: LEGAL_EFFECTIVE_DATE,
    status: 'Current terms',
  },
  cookies: {
    version: 'cookies-2026-09-03-en',
    effectiveDate: LEGAL_EFFECTIVE_DATE,
    status: 'Current notice',
  },
  security: {
    version: 'security-2026-09-03-en',
    effectiveDate: LEGAL_EFFECTIVE_DATE,
    status: 'Current information',
  },
  dpa: {
    version: 'dpa-model-2026-09-03-en',
    effectiveDate: LEGAL_EFFECTIVE_DATE,
    status: 'Contract template',
  },
  subprocessors: {
    version: 'subprocessors-2026-09-03-en',
    effectiveDate: LEGAL_EFFECTIVE_DATE,
    status: 'Current list',
  },
  deletion: {
    version: 'deletion-2026-09-03-en',
    effectiveDate: LEGAL_EFFECTIVE_DATE,
    status: 'Current procedure',
  },
} as const;

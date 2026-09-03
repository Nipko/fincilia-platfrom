export const LEGAL_EFFECTIVE_DATE = '3 de septiembre de 2026';

export const TERMS_VERSION = 'terms-2026-09-03';
export const PRIVACY_VERSION = 'privacy-2026-09-03';

export const LEGAL_DOCUMENTS = {
  privacy: {
    version: PRIVACY_VERSION,
    effectiveDate: LEGAL_EFFECTIVE_DATE,
    status: 'Política vigente',
  },
  terms: {
    version: TERMS_VERSION,
    effectiveDate: LEGAL_EFFECTIVE_DATE,
    status: 'Términos vigentes',
  },
  cookies: {
    version: 'cookies-2026-09-03',
    effectiveDate: LEGAL_EFFECTIVE_DATE,
    status: 'Aviso vigente',
  },
  security: {
    version: 'security-2026-09-03',
    effectiveDate: LEGAL_EFFECTIVE_DATE,
    status: 'Información vigente',
  },
  dpa: {
    version: 'dpa-model-2026-09-03',
    effectiveDate: LEGAL_EFFECTIVE_DATE,
    status: 'Modelo contractual',
  },
  subprocessors: {
    version: 'subprocessors-2026-09-03',
    effectiveDate: LEGAL_EFFECTIVE_DATE,
    status: 'Lista vigente',
  },
  deletion: {
    version: 'deletion-2026-09-03',
    effectiveDate: LEGAL_EFFECTIVE_DATE,
    status: 'Procedimiento vigente',
  },
} as const;

import type { LegalSection } from '@/components/legal-document';

const CONTROLLER = 'Parallext LLC';
const ADDRESS = '7345 W Sand Lake Rd, Ste 210, Office 2812, Orlando, Florida 32819, United States';
const PHONE = '+57 313 432 8491';

export const PRIVACY_SECTIONS: readonly LegalSection[] = [
  {
    title: 'Controller, processor, and scope',
    paragraphs: [
      `Fincilia is operated by ${CONTROLLER} and developed under the Parallext.com brand. For account, security, billing, support, and website-use data, ${CONTROLLER} acts as the data controller. Contact address: ${ADDRESS}. Phone: ${PHONE}.`,
      'When an organization uses Fincilia to process documents or financial information under its own instructions, that organization determines the business purposes and Parallext LLC acts as its data processor or service provider under the applicable contract and, where relevant, a Data Processing Agreement (DPA).',
      'Contact privacy@fincilia.com for personal-data matters, legal@fincilia.com for contractual matters, and support@fincilia.com for general support.',
    ],
  },
  {
    title: 'Information we process',
    bullets: [
      'Identity and account data: identity-provider identifier, display name, verified email address, account status, organization, memberships, and roles. Fincilia does not receive or store your Google password.',
      'Security and operations data: sessions, access and audit events, IP address and limited technical metadata, failed attempts, diagnostics, and signals needed to prevent abuse.',
      'Service data: company settings, sources, documents, columns, transactions, reconciliations, notes, and evidence that an organization chooses to upload when the relevant environment is authorized.',
      'Support and communications data: requests, notification preferences, operational messages, and information you choose to include when contacting us.',
      'Billing data: plan, usage, billing country, and payment references when a payment provider is enabled. Fincilia will not store full card numbers or security codes.',
      'Website data: strictly necessary cookies and minimum technical data described in our Cookie Notice. We do not use behavioral advertising or cross-site tracking.',
    ],
  },
  {
    title: 'Purposes and lawful grounds',
    bullets: [
      'Create and administer your account, authenticate you, resolve permissions, and provide the features you request.',
      'Process business information according to the documented instructions of the organization that controls that information.',
      'Protect the platform, detect abuse, investigate incidents, preserve traceability, and comply with applicable legal obligations.',
      'Handle support, inquiries, complaints, privacy requests, and operational communications.',
      'Manage plans, usage, payments, and taxes when billing is enabled.',
      'Measure reliability and improve the service through minimized metrics. We do not use financial documents to train artificial-intelligence models without separate authorization and agreement.',
    ],
    paragraphs: [
      'We obtain prior, informed authorization when required by law and preserve evidence of the version accepted. We may also process information when necessary to provide the requested service, protect the platform, or meet an applicable obligation, always within legal limits. Optional marketing communications require a separate choice.',
    ],
  },
  {
    title: 'Sign in with Google',
    paragraphs: [
      'If you choose to continue with Google, Fincilia requests only openid, email, and profile. Google provides a stable identifier, verified email address, and display name so that we can authenticate you and create or locate your Fincilia profile. We do not request access to Gmail, Google Drive, contacts, calendars, or files in your Google Account.',
      'We access, use, and store this Google account data only for identity, security, account creation, and related support. We do not sell it, use it for advertising, send it to artificial-intelligence models, or share it except with service providers needed to operate authentication and the service.',
      'Our use and transfer of information received from Google APIs is limited to the purposes described here and complies with the Google API Services User Data Policy, including the Limited Use requirements.',
    ],
  },
  {
    title: 'Recipients, service providers, and international transfers',
    paragraphs: [
      'We may disclose information to the organization you belong to, its authorized administrators, contracted providers acting under instructions, and authorities when required by a valid legal obligation. We do not sell personal data.',
      'Fincilia\'s primary evaluated infrastructure is hosted by Amazon Web Services in the São Paulo, Brazil region. Google supports authentication; Namecheap Private Email provides contact mailboxes; and Cloudflare manages DNS and may provide network controls if enabled. The current list and purposes are published at /subencargados.',
      'When processing involves an international data transmission or transfer, we apply the applicable contract, documented instructions, security measures, and legally required safeguards. A business customer may request a DPA before enabling its own data.',
    ],
  },
  {
    title: 'Retention and deletion',
    paragraphs: [
      'We retain each category only for as long as necessary for the account, contract, disclosed purpose, security, or an applicable obligation. Accounts are retained while active; after termination, access is blocked and the account enters the deletion process, except where justified retention is required.',
      'Documents and financial records follow the organization\'s instructions, the related accounting period, and the agreed schedule. Security, billing, authorization, and decision records may be retained as needed for audit, legal claims, and legal obligations. Backups are deleted through rotation, and valid deletion requests are reapplied through deletion markers before service restoration.',
      'Specific periods for business data are documented in the applicable contract or retention schedule. Fincilia does not retain information indefinitely for convenience and does not claim deletion is complete while unjustified active copies remain.',
    ],
  },
  {
    title: 'Your rights and how to exercise them',
    paragraphs: [
      'You may request access, correction, updating, proof of authorization, information about use, withdrawal of authorization, or deletion by writing from your associated email address to privacy@fincilia.com. State the right you want to exercise and provide enough detail; do not email passwords or financial documents. We verify identity and authority before responding.',
      'For requests governed by Colombian law, inquiries are answered within ten business days and may be extended by five business days with notice; complaints are answered within fifteen business days and may be extended by eight business days with notice. Any shorter mandatory period in another jurisdiction will apply.',
      'If Parallext LLC acts as a processor for an organization, we coordinate the request with that organization as controller. Data subjects in Colombia may contact the Superintendence of Industry and Commerce after completing the applicable procedure before the controller or processor.',
    ],
  },
  {
    title: 'Security, children, and changes',
    paragraphs: [
      'We apply technical and organizational controls designed for company isolation, least-privilege access, encryption, auditability, backups, and incident response. No system eliminates all risk; report an incident or vulnerability to security@fincilia.com.',
      'Fincilia is a business service and is not directed to anyone under 18. If we learn that a minor created an account without valid authority, we will suspend it and coordinate its deletion.',
      'We publish a new version when purposes, categories, providers, or rights change materially. If a change requires renewed authorization, we request it before applying the change. This version is effective from the date shown at the top of this document.',
    ],
  },
];

export const TERMS_SECTIONS: readonly LegalSection[] = [
  {
    title: 'Parties, acceptance, and eligibility',
    paragraphs: [
      `These Terms govern use of Fincilia, a product operated by ${CONTROLLER}, whose contact address is ${ADDRESS}. By creating an account or using the service, you accept this version of the Terms and acknowledge the Privacy Policy.`,
      'You must be at least 18 and able to enter into a binding agreement. If you act for a company, accounting firm, or other organization, you represent that you have authority to accept these Terms on its behalf. If a signed order form or agreement exists, that document controls in the event of a conflict.',
    ],
  },
  {
    title: 'Service and UAT environment',
    paragraphs: [
      'Fincilia helps upload, structure, clean, compare, and review financial information with traceability. Its results are decision-support tools and require human validation; they are not an audit, certification, or legal, tax, accounting, or financial advice.',
      'The UAT environment may be reset, changed, or suspended for testing and corrections. While Fincilia states that use is limited to synthetic data, you must not upload real personal, financial, banking, tax, or confidential data. Real data may be enabled only through an expressly authorized environment and subject to the applicable agreements.',
    ],
  },
  {
    title: 'Accounts, organizations, and roles',
    bullets: [
      'You must provide accurate information, protect your access, and promptly notify security@fincilia.com of unrecognized activity.',
      'Google may verify your identity, but Fincilia determines organizations, companies, roles, and permissions on its own servers.',
      'Organization administrators are responsible for granting and revoking access, confirming user authority, and maintaining appropriate separation of duties.',
      'You must not share sessions, impersonate others, or attempt to access companies or data you are not authorized to use.',
    ],
  },
  {
    title: 'Customer content and responsibilities',
    paragraphs: [
      'You retain rights in content you upload. You grant Parallext LLC a limited permission to host, reproduce, transform, and transmit it only as needed to provide, secure, and support Fincilia under your instructions and the Privacy Policy.',
      'You are responsible for having sufficient rights, permissions, and authorizations for the content; reviewing configurations, mappings, reconciliations, and closes; and preserving originals required by your obligations. Fincilia does not replace your internal controls or the professional responsibility of an accountant, administrator, or auditor.',
    ],
  },
  {
    title: 'Acceptable use',
    bullets: [
      'Do not use Fincilia for fraud, unlawful conduct, malware, harassment, infringement, or unauthorized processing of data.',
      'Do not bypass access controls, isolation, limits, audit controls, or security, and do not conduct load or vulnerability testing without written authorization.',
      'Do not unlawfully copy, resell, sublicense, reverse engineer, or present Fincilia as your own service.',
      'Do not upload secrets, banking credentials, passwords, full card numbers, or security codes.',
      'Report vulnerabilities privately and do not publish exploitable information before coordinating a correction.',
    ],
  },
  {
    title: 'Intellectual property and feedback',
    paragraphs: [
      'Fincilia and its software, design, documentation, trademarks, and components belong to Parallext LLC or its licensors. These Terms do not transfer ownership of the service or another customer\'s content.',
      'You may submit voluntary suggestions. Parallext LLC may use them to improve the product without payment, while seeking not to identify you publicly or disclose confidential information.',
    ],
  },
  {
    title: 'Plans, payments, and changes',
    paragraphs: [
      'UAT is free unless otherwise agreed in writing. When paid plans are enabled, prices, taxes, renewal, limits, and cancellation terms will be shown before purchase or stated in an order form. We will not charge you based solely on this UAT version.',
      'We may change features to improve security, compliance, or usefulness. We will give notice of material changes to these Terms through the application or account email and request renewed acceptance when appropriate.',
    ],
  },
  {
    title: 'Suspension, termination, and data',
    paragraphs: [
      'We may restrict or suspend access because of a security risk, unlawful use, material breach, or urgent operational need. When reasonable, we will provide an opportunity to cure before terminating the account.',
      'You may stop using the service and request deletion as described at /eliminar-cuenta. Before ordinary termination, you may request an export when that feature is available and you are authorized. Termination does not end obligations that by their nature survive, including confidentiality, ownership, outstanding payment, and justified legal retention.',
    ],
  },
  {
    title: 'Warranties and limitation of liability',
    paragraphs: [
      'During UAT, Fincilia is provided for evaluation and may contain errors or interruptions. To the maximum extent permitted by law, it is provided without implied warranties of uninterrupted availability, fitness for a particular purpose, or complete absence of errors.',
      'To the maximum extent permitted by law, Parallext LLC is not liable for indirect damages, lost profits, or accounting decisions made without human review. Total liability arising from the service will not exceed the greater of the fees paid by the customer during the twelve months before the event or USD 100. This limitation does not apply to fraud, willful misconduct, gross negligence, or rights that cannot legally be limited.',
    ],
  },
  {
    title: 'Governing law, disputes, and contact',
    paragraphs: [
      'These Terms are governed by the laws of the State of Florida, United States, without excluding mandatory data-protection or consumer laws that apply. Disputes that cannot be resolved directly will be submitted to the competent courts of Orange County, Florida, unless mandatory law permits another jurisdiction.',
      `Notices to Parallext LLC may be sent to legal@fincilia.com or ${ADDRESS}. Contact support@fincilia.com for support. Phone: ${PHONE}.`,
    ],
  },
];

export const COOKIE_SECTIONS: readonly LegalSection[] = [
  {
    title: 'Strictly necessary cookies',
    bullets: [
      'fincilia_session: an httpOnly cookie that maintains the authenticated session until the token expires.',
      'fincilia_session_name: the display name used by the interface during the same session; it contains no permissions and does not determine access.',
      'fincilia_oidc_tx: an encrypted httpOnly cookie that stores state, nonce, and the PKCE verifier for no more than ten minutes while Google sign-in completes.',
      'Amazon Cognito or Google cookies: these may appear on their own domains during authentication and are governed by those providers\' policies.',
    ],
  },
  {
    title: 'Purpose, control, and duration',
    paragraphs: [
      'These cookies are necessary to authenticate users, prevent request forgery, maintain the session, and complete sign-in securely. We do not use advertising cookies, third-party analytics, or cross-site tracking.',
      'You can delete them through your browser; doing so will sign you out or interrupt an ongoing sign-in. Session cookies expire with the token, temporary OAuth cookies expire after ten minutes, and all Fincilia cookies are removed when you sign out.',
    ],
  },
  {
    title: 'Future changes',
    paragraphs: [
      'If we add analytics or optional cookies, we will update this notice with the provider, purpose, and duration and request consent before enabling them where required. Send questions to privacy@fincilia.com.',
    ],
  },
];

export const SECURITY_SECTIONS: readonly LegalSection[] = [
  {
    title: 'Service controls',
    bullets: [
      'Company isolation through server-side authorization and forced PostgreSQL row-level security policies.',
      'Encryption in transit, secrets kept outside source code, short-lived sessions, and managed authentication through Google and Amazon Cognito when enabled.',
      'Exact-decimal money, append-only audit records, and lineage for financial facts.',
      'Digest-pinned images, separated migrations, least privilege, and cloud administration without public SSH access.',
      'Backups, deletion markers, and restoration checks designed to prevent deleted data from reappearing.',
    ],
  },
  {
    title: 'Shared responsibility',
    paragraphs: [
      'Parallext LLC protects the infrastructure and service; each organization must properly administer its users, roles, devices, exports, and content. No control eliminates all risk, and UAT features do not constitute a security certification.',
      'Do not send secrets or documents by email. Use only authorized upload flows and always confirm the environment and company before operating.',
    ],
  },
  {
    title: 'Responsible reporting',
    paragraphs: [
      'Send findings privately to security@fincilia.com with a description, impact, and minimum reproduction steps. Do not access another party\'s data, disrupt the service, or publish exploitable details before coordinating a correction. We will acknowledge receipt and provide reasonable progress updates.',
    ],
  },
];

export const DPA_SECTIONS: readonly LegalSection[] = [
  {
    title: 'When it applies',
    paragraphs: [
      'This page describes Parallext LLC\'s Data Processing Agreement model for organizations that use Fincilia with their own data. It is not executed merely by accepting the web Terms. The applicable DPA must identify the parties, contracted service, and effective date.',
    ],
  },
  {
    title: 'Agreement contents',
    bullets: [
      'Subject matter, duration, nature, purposes, instructions, and categories of data and data subjects.',
      'Controller and processor roles, confidentiality obligations, and technical and organizational measures.',
      'Subprocessors, locations, international transmissions or transfers, and an objection mechanism.',
      'Assistance with rights requests, incidents, assessments, audits, and authority requests.',
      'Return, export, deletion, legal hold, backups, evidence, and termination.',
      'Security, region, contact, service-level, and retention-schedule annexes.',
    ],
  },
  {
    title: 'How to request it',
    paragraphs: [
      'Email legal@fincilia.com with your organization, country, data types, and use case. Do not attach real documents. Parallext LLC will provide the model and applicable annexes before the requested processing is enabled.',
    ],
  },
];

export const SUBPROCESSOR_SECTIONS: readonly LegalSection[] = [
  {
    title: 'Current or planned providers',
    bullets: [
      'Amazon Web Services, Inc.: computing, networking, storage, databases, secrets, technical logs, and managed identity. Planned primary region: sa-east-1, São Paulo, Brazil.',
      'Google LLC: optional identity provider for openid, email, and profile. It receives neither Fincilia financial documents nor access to Gmail, Drive, contacts, or calendars.',
      'Namecheap, Inc. / Private Email: sending and receiving communications for @fincilia.com mailboxes.',
      'Cloudflare, Inc.: authoritative DNS, domain management, and, if expressly enabled, edge network and security controls.',
    ],
  },
  {
    title: 'Access and limits',
    paragraphs: [
      'Providers receive only the information needed for their function and are subject to contractual terms and access controls. Parallext LLC does not authorize any provider to sell data, create behavioral advertising, or train models using customer documents.',
      'Exact locations may vary because of support, resilience, or a provider\'s global services. Organizations requiring specific residency or restrictions must agree to them in writing before uploading data.',
    ],
  },
  {
    title: 'Changes and objections',
    paragraphs: [
      'We will publish material changes before a new provider processes business data. Customers with a DPA will receive the notice and objection period defined in that agreement. Send questions to privacy@fincilia.com.',
    ],
  },
];

export const DELETION_SECTIONS: readonly LegalSection[] = [
  {
    title: 'Request deletion',
    paragraphs: [
      'Write from your associated email address to privacy@fincilia.com with the subject “Delete my Fincilia account,” stating whether you want to delete your profile, an organization you administer, or specific information. Do not include passwords, documents, or financial information. We may request additional verification to prevent unauthorized deletion.',
      'We acknowledge receipt and classify the request as an inquiry or complaint under applicable law. For Colombia, the periods in the Privacy Policy apply: ten business days for inquiries and fifteen business days for complaints, including permitted notified extensions.',
    ],
  },
  {
    title: 'Scope and execution',
    bullets: [
      'We block access and verify authority, memberships, objects, exports, jobs, and related events.',
      'We assess contractual or legal obligations; any retention is limited, documented, and disclosed when possible.',
      'We record a deletion marker before purging active and derived copies and reapply it when restoring backups.',
      'We explain what was deleted, what temporarily remains, and the estimated date or condition for completing reconciliation.',
      'Deleting a user does not automatically delete records that belong to an organization and that the organization must retain; in that case, access is revoked and identity data is minimized as appropriate.',
    ],
  },
  {
    title: 'Google and third parties',
    paragraphs: [
      'Deleting your Fincilia account does not delete your Google Account. You may also remove Fincilia\'s access from your Google Account settings. Fincilia will stop using the link and retain only the minimum evidence required for security or law.',
      'For messages already sent to our mailboxes or data administered by your organization, we coordinate the request with the relevant provider or controller.',
    ],
  },
];

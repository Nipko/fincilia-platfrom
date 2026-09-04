# Fincilia UAT provider and subprocessor register

Status: **technical inventory complete; independent legal review pending**.

This register is a factual operating inventory, not legal advice or approval of
an international transfer. It distinguishes the product runtime from identity,
DNS, contact email and development tooling. Until the required human review is
recorded, A-02, DRG-00 and DRG-01 remain closed and only synthetic data is
allowed.

| Provider | Current role | Data currently allowed | Hard boundary |
| --- | --- | --- | --- |
| Amazon Web Services | Product runtime and managed identity in `sa-east-1` | Synthetic test data, operational metadata and identity configuration | Real financial documents remain blocked until DRG-01 |
| Google | Federated identity | Stable OIDC subject, verified email and display name | No Gmail, Drive, contacts, calendars or financial documents |
| Cloudflare | Authoritative DNS and domain management | DNS-query and domain-account metadata | Application proxy is currently disabled; no financial payload |
| Namecheap Private Email | Business contact mailboxes | Business correspondence and mailbox metadata | No product email ingestion and no financial documents by email |
| GitHub | Development and release supply chain | Source, synthetic fixtures and build metadata | It is not in the runtime data path; no customer documents, PII or secrets |

The exact purposes, sources and unresolved contract questions are in
`subprocessor-register.json`. Regional AWS services are configured in São
Paulo, but that fact does not prove the location of every support or control
plane operation. Google authentication is a global provider service and must be
classified separately. Cloudflare or Namecheap must not be inferred to receive
application data merely because they operate DNS or mail.

## Independent review still required

Legal and Privacy must classify the role and transfer/transmission mechanism by
activity, review the applicable DPAs and subprocessor change/objection terms,
and verify the public disclosure. Security must confirm that the technical data
paths match this register. The reviewer records only a stable professional
alias and an external evidence reference in Git, never identity documents or a
signature image.

Primary sources include the AWS DPA and subprocessor list, AWS regional-service
documentation, Google OAuth/OIDC policies, Cloudflare DPA and trust register,
Namecheap privacy terms, GitHub DPA/subprocessor disclosures, Colombia's Law
1581 of 2012 and the SIC's 2026 cross-border processing guidance.

## Verification

```text
python -m tools.subprocessor_register.cli validate
python -m tools.subprocessor_register.cli report
python -m unittest tools.subprocessor_register.test_model
```

`ok: true` means the inventory is internally consistent and ready for human
review. It never means that a provider, region, DPA or real-data flow is
approved.

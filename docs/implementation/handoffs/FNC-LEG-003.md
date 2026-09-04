---
id: FNC-LEG-003-R1
status: REVIEW_PENDING
base_sha: 38c785e68ae2660ee585ab5839d7c7e4ed168ae7
integration_sha: pending_integration_steward
data_ceiling: synthetic_only_until_gate
gate_effect: evidence_only
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Legal, Privacy, Security, Platform/SRE]
---

# Handoff FNC-LEG-003 R1 — provider and subprocessor register

## Result

Fincilia now has a versioned, executable inventory of the five providers in
the current UAT design: AWS, Google, Cloudflare, Namecheap and GitHub. The
register separates product runtime, federated identity, authoritative DNS,
contact email and development supply-chain planes instead of labelling every
provider as a generic subprocessor.

The data boundary is fail-closed. AWS is the only intended future destination
for financial documents and that path remains blocked until DRG-01. Google is
limited to OIDC `openid`, `email` and `profile`; Cloudflare is DNS-only;
Namecheap is contact-email only; GitHub is outside the runtime data path.
External AI, email ingestion, connectors and real financial data remain
disabled.

## Sources and disclosure

Thirteen dated primary sources point to the providers' official DPA, privacy,
subprocessor, OAuth/OIDC and regional-service materials, plus Colombia's Law
1581 and current SIC guidance. Only URLs and retrieval dates are stored; source
text is not copied. The validator also checks the public legal disclosure for
AWS, Google, Cloudflare and Namecheap.

An AWS resource being regional in `sa-east-1` is not treated as proof that all
support or control-plane processing is regional. That question remains
explicitly assigned to independent review.

## Verification

- `python3 -m unittest tools.subprocessor_register.test_model -v`: 10 tests,
  all passed after correcting duplicate-ID detection.
- `python3 -m tools.subprocessor_register.cli validate`: `ok: true`, five
  providers, thirteen sources, `human_approval: false`,
  `real_data_authorized: false`.
- Combined legal, region, privacy and work-graph regression: 112 tests, all
  passed after resolving the canonical handoff-path finding.

The adversarial suite rejects duplicate or missing providers, unofficial or
credentialed source URLs, broader Google scopes, Cloudflare proxying,
Namecheap ingestion, GitHub runtime data, overstated AWS locality, invented
legal approvals and prematurely opened gates.

## Human review and gates

Legal and Privacy must independently classify each activity, decide the
international transfer/transmission mechanism, assess DPA sufficiency and the
subprocessor objection process. Security must confirm that deployed data paths
match the register; Platform/SRE must confirm the regional resource inventory.

No review identity or decision was invented. A-02, DRG-00 and DRG-01 remain
`not_met`; this packet prepares review but does not authorize real data,
deployment or a pilot.

## Rollback

Reverting this task removes an offline inventory, validator, tests and CI lane.
It does not modify provider accounts, contracts, DNS, AWS resources or user
data.

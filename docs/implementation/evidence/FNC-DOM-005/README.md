# Evidence FNC-DOM-005

- Date: 2026-08-21
- Declared and verified base: `a43bc1c`
- Integration base: `5fb0220`
- Data classification: synthetic only
- Technical result: PASS
- Human acceptance: pending Data, Accounting, Architecture, Security and Privacy

## Reproducible result

| Command | Result |
|---|---:|
| `python -m tools.lineage_model.validate` | PASS, no errors |
| `python -m unittest tools.lineage_model.test_validate -v` | PASS, 76/76 |
| Integrated repository Python suite | PASS, 339/339 |
| Repository quality gate on indexed routes | PASS |

The validator is offline and deterministic. Its pure functions exercise a synthetic lineage graph, ordered overlay application and canonical reproduction-key calculation. No customer document, external model or network input is used.

## Coverage

- Six typed locator families and ten node types.
- Five mandatory end-to-end paths with 100% field coverage.
- Append-only overlays, stale-base conflicts, independent review and explicit reversal.
- Engine release and reproduction manifest without floating versions.
- Privacy/retention bindings and honest behavior after tombstone deletion.
- Dynamic coverage of canonical entities marked `lineage_required`.
- 76 positive and negative tests, including the required LIN, OVR, PAR, PRV and DED scenarios plus live DFD/TM-015 cross-contract checks.

## Review findings preserved

The following are not silently resolved: physical storage cost for field-level lineage, personal-data taxonomy, legal retention order, release approver, external model pinning, and vocabulary drift between architecture/DFD stores and classifications. They remain routed to their human owners.

The previously missing first-class `issued_authorization_context` is now exercised separately by FNC-PLT-005 at integration commit `5fb0220`; that does not close the remaining authorization issuance and audit work.

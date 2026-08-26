from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MODEL = Path("docs/implementation/founder-governance.json")

EXPECTED_DECISIONS = {
    "UD-DR-PRV-001",
    "UD-ISSUED-CONTEXT",
    "UD-LOCATOR-STORAGE",
    "UD-PORTFOLIO-CANDIDATES",
    "UD-PRIMARY-OPERATOR",
    "UD-QA-CATALOG-DRIFT",
    "UD-QA-CATALOG-FORMAT",
    "UD-QA-CATALOG-OWNER",
    "UD-QA-MUTATION-TOOLING",
    "UD-RELEASE-APPROVAL",
}
EXPECTED_ADRS = {f"ADR-{number:03d}" for number in range(1, 11)} | {"ADR-023", "ADR-024"}
EXPECTED_ROLES = {"Integration", "Product", "Accounting", "Architecture", "Security", "Privacy", "Legal"}
REQUIRED_LIMITS = {
    "data_ceiling": "synthetic_only",
    "s1_ready_automatically_met": False,
    "drg_00_automatically_met": False,
    "drg_01_automatically_met": False,
    "production_authorized": False,
    "real_financial_data_authorized": False,
}


@dataclass(frozen=True)
class Finding:
    code: str
    subject: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return self.__dict__


def validate_model(model: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    founder = model.get("founder") or {}
    if founder != {
        "id": "FOUNDER-01",
        "kind": "stable_pseudonymous_human_alias",
        "identity_mapping": "offline_only",
    }:
        findings.append(Finding("FG-IDENTITY", "founder", "stable pseudonymous founder identity required"))

    if set(model.get("accountable_roles") or []) != EXPECTED_ROLES:
        findings.append(Finding("FG-ROLES", "accountable_roles", "all provisional accountable roles are required"))

    review = model.get("independent_review") or {}
    if review.get("founder_counts_as_independent_reviewer") is not False:
        findings.append(Finding("FG-SOD", "independent_review", "Founder must never count as an independent reviewer"))
    if review.get("state") != "pending_distinct_humans":
        findings.append(Finding("FG-SOD", "independent_review.state", "distinct human reviews remain pending"))
    if set(review.get("required_roles") or []) != {"Accounting", "Database", "Privacy_or_Legal", "Security"}:
        findings.append(Finding("FG-SOD", "independent_review.required_roles", "independent review roles drifted"))

    decisions = model.get("approved_decisions") or []
    ids = [item.get("id") for item in decisions if isinstance(item, dict)]
    if set(ids) != EXPECTED_DECISIONS or len(ids) != len(set(ids)) or any(not item.get("decision") for item in decisions):
        findings.append(Finding("FG-DECISIONS", "approved_decisions", "the approved package must contain exactly ten explained decisions"))

    if set(model.get("approved_adrs") or []) != EXPECTED_ADRS:
        findings.append(Finding("FG-ADRS", "approved_adrs", "the Founder-approved ADR package drifted"))
    if set((model.get("adr_decisions") or {}).keys()) != {"ADR-002", "ADR-008", "ADR-024"}:
        findings.append(Finding("FG-ADR-DETAIL", "adr_decisions", "specific ADR selections are incomplete"))
    if set(model.get("excluded_adrs_pending_independent_review") or []) != {"ADR-026", "ADR-027"}:
        findings.append(Finding("FG-EXCLUSIONS", "excluded_adrs_pending_independent_review", "sensitive ADR exclusions drifted"))
    if model.get("limits") != REQUIRED_LIMITS:
        findings.append(Finding("FG-LIMITS", "limits", "approval must not widen data or release gates"))
    if model.get("decision_id") != "IMP-017" or model.get("approved_at") != "2026-08-25":
        findings.append(Finding("FG-EVIDENCE", "decision", "approval reference or date missing"))
    return findings


def validate_repository(root: Path = ROOT) -> tuple[dict[str, Any], list[Finding]]:
    model = json.loads((root / MODEL).read_text(encoding="utf-8"))
    findings = validate_model(model)
    return {
        "founder": (model.get("founder") or {}).get("id"),
        "approved_decisions": len(model.get("approved_decisions") or []),
        "approved_adrs": len(model.get("approved_adrs") or []),
        "independent_review": (model.get("independent_review") or {}).get("state"),
    }, findings


def main() -> int:
    report, findings = validate_repository()
    print(json.dumps({"ok": not findings, "report": report, "errors": [item.as_dict() for item in findings]}, indent=2, sort_keys=True))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())

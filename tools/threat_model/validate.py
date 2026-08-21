from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REQUIRED_ASSETS = {f"A{index:02d}" for index in range(1, 13)}
REQUIRED_RISKS = {f"TM-{index:03d}" for index in range(1, 16)}
REQUIRED_TAGS = {
    "cross_company",
    "pool_context",
    "authorization_escalation",
    "revocation",
    "hostile_input_pan",
    "worker_escape",
    "completeness",
    "safe_dedupe",
    "replay_idempotency",
    "ai_prompt_injection",
    "telemetry_leak",
    "export_scope",
    "audit_integrity",
    "restore_resurrection",
    "supply_chain",
}
REQUIRED_METHODS = {"STRIDE", "business_abuse", "accounting_integrity", "privacy"}
TREATMENTS = {"mitigate", "avoid_and_mitigate", "transfer_and_mitigate"}
EVIDENCE_STATES = {"passed_spike", "planned"}
SPECIAL_CONTROLS = {
    "cross_company": {"C-COMPANY", "C-RLS"},
    "pool_context": {"C-RLS", "C-WORKER"},
    "authorization_escalation": {"C-AUTH", "C-AUDIT"},
    "revocation": {"C-REVOKE"},
    "hostile_input_pan": {"C-QUAR", "C-SCAN"},
    "worker_escape": {"C-WORKER", "C-MANIFEST"},
    "completeness": {"C-COMPLETE", "C-DECIMAL"},
    "safe_dedupe": {"C-IDEMP", "C-LINEAGE"},
    "replay_idempotency": {"C-IDEMP", "C-SIGN"},
    "ai_prompt_injection": {"C-AI", "C-EGRESS"},
    "telemetry_leak": {"C-LOG"},
    "export_scope": {"C-EXPORT", "C-REVOKE"},
    "audit_integrity": {"C-AUDIT"},
    "restore_resurrection": {"C-DELETE", "C-RESTORE"},
    "supply_chain": {"C-MANIFEST", "C-LINEAGE"},
}


@dataclass(frozen=True, order=True)
class ThreatModelError:
    code: str
    location: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _severity(score: int) -> str:
    if score <= 4:
        return "low"
    if score <= 9:
        return "medium"
    if score <= 16:
        return "high"
    return "critical"


def _validate_score(block: Any, location: str, errors: list[ThreatModelError]) -> int | None:
    if not isinstance(block, dict):
        errors.append(ThreatModelError("TM-SCORE-BLOCK", location, "score block must be an object"))
        return None
    likelihood = block.get("likelihood")
    impact = block.get("impact")
    score = block.get("score")
    if likelihood not in {1, 2, 3, 4, 5} or impact not in {1, 2, 3, 4, 5}:
        errors.append(ThreatModelError("TM-SCORE-RANGE", location, "likelihood and impact must be 1 through 5"))
        return None
    expected = likelihood * impact
    if score != expected:
        errors.append(ThreatModelError("TM-SCORE-FORMULA", location, f"score must equal {expected}"))
    if block.get("severity") != _severity(expected):
        errors.append(ThreatModelError("TM-SCORE-SEVERITY", location, "severity does not match score band"))
    return expected


def _ids(items: Any) -> set[str]:
    if not isinstance(items, list):
        return set()
    return {
        item.get("id")
        for item in items
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }


def _require_text(risk: dict[str, Any], risk_id: str, field: str, errors: list[ThreatModelError]) -> None:
    value = risk.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(ThreatModelError("TM-RISK-FIELD", f"risks.{risk_id}.{field}", "non-empty text is required"))


def validate_model(
    model: dict[str, Any],
    dfd_model: dict[str, Any],
    repository_root: Path | None = None,
) -> list[ThreatModelError]:
    errors: list[ThreatModelError] = []
    if model.get("schema_version") != 1:
        errors.append(ThreatModelError("TM-SCHEMA-VERSION", "$", "schema_version must equal 1"))
    if model.get("task_id") != "FNC-SEC-002":
        errors.append(ThreatModelError("TM-TASK", "task_id", "task_id must be FNC-SEC-002"))
    if model.get("data_ceiling") != "synthetic_only":
        errors.append(ThreatModelError("TM-DATA-CEILING", "data_ceiling", "E0 permits synthetic_only"))
    if set(model.get("method", [])) != REQUIRED_METHODS:
        errors.append(ThreatModelError("TM-METHOD", "method", "required analysis methods must be declared"))

    asset_ids = _ids(model.get("assets"))
    if asset_ids != REQUIRED_ASSETS or len(model.get("assets", [])) != len(REQUIRED_ASSETS):
        errors.append(ThreatModelError("TM-ASSETS", "assets", "A01 through A12 must be declared exactly once"))
    declared_tags = set(model.get("required_scenario_tags", []))
    if declared_tags != REQUIRED_TAGS:
        errors.append(ThreatModelError("TM-REQUIRED-TAGS", "required_scenario_tags", "required scenario tags must be exact"))

    dfd_threats = _ids(dfd_model.get("threat_catalog"))
    dfd_controls = _ids(dfd_model.get("control_catalog"))
    dfd_tests = _ids(dfd_model.get("negative_test_catalog"))
    dfd_flows = _ids(dfd_model.get("flows"))

    risks = model.get("risks")
    if not isinstance(risks, list):
        return sorted(set(errors + [ThreatModelError("TM-RISKS", "risks", "risks must be a list")]))
    risk_ids = [risk.get("id") for risk in risks if isinstance(risk, dict)]
    if set(risk_ids) != REQUIRED_RISKS or len(risk_ids) != len(REQUIRED_RISKS):
        errors.append(ThreatModelError("TM-RISK-SET", "risks", "TM-001 through TM-015 must be declared exactly once"))

    covered_threats: set[str] = set()
    covered_flows: set[str] = set()
    covered_tags: set[str] = set()
    for risk in risks:
        if not isinstance(risk, dict) or not isinstance(risk.get("id"), str):
            errors.append(ThreatModelError("TM-RISK-ID", "risks", "every risk requires a string id"))
            continue
        risk_id = risk["id"]
        for field in ("title", "threat_actor", "preconditions", "scenario", "impact", "owner_role", "target_gate", "status"):
            _require_text(risk, risk_id, field, errors)

        tags = risk.get("scenario_tags")
        if not isinstance(tags, list) or not tags:
            errors.append(ThreatModelError("TM-RISK-TAGS", f"risks.{risk_id}", "scenario tag is required"))
            tags = []
        for tag in tags:
            if tag not in REQUIRED_TAGS:
                errors.append(ThreatModelError("TM-RISK-TAG-UNKNOWN", f"risks.{risk_id}", f"unknown tag {tag!r}"))
        covered_tags.update(tag for tag in tags if tag in REQUIRED_TAGS)

        references = (
            ("dfd_threats", dfd_threats, covered_threats),
            ("flows", dfd_flows, covered_flows),
            ("assets", asset_ids, set()),
            ("controls", dfd_controls, set()),
            ("negative_tests", dfd_tests, set()),
        )
        for field, known, coverage in references:
            values = risk.get(field)
            if not isinstance(values, list) or not values:
                errors.append(ThreatModelError("TM-RISK-REFERENCE", f"risks.{risk_id}.{field}", "non-empty references are required"))
                values = []
            for value in values:
                if value not in known:
                    errors.append(ThreatModelError("TM-RISK-REFERENCE-UNKNOWN", f"risks.{risk_id}.{field}", f"unknown reference {value!r}"))
            coverage.update(value for value in values if value in known)

        categories = risk.get("categories")
        if not isinstance(categories, list) or not categories:
            errors.append(ThreatModelError("TM-RISK-CATEGORY", f"risks.{risk_id}", "at least one category is required"))

        inherent_score = _validate_score(risk.get("inherent"), f"risks.{risk_id}.inherent", errors)
        residual = risk.get("residual")
        residual_score = _validate_score(residual, f"risks.{risk_id}.residual", errors)
        if inherent_score is not None and residual_score is not None and residual_score > inherent_score:
            errors.append(ThreatModelError("TM-RESIDUAL-INCREASE", f"risks.{risk_id}.residual", "projected residual cannot exceed inherent score"))
        if isinstance(residual, dict):
            if residual.get("basis") != "projected_after_controls":
                errors.append(ThreatModelError("TM-RESIDUAL-BASIS", f"risks.{risk_id}.residual", "residual must be explicitly projected"))
            if residual.get("validation_state") != "projected_not_accepted":
                errors.append(ThreatModelError("TM-RESIDUAL-ACCEPTANCE", f"risks.{risk_id}.residual", "agent cannot accept residual risk"))

        if risk.get("treatment") not in TREATMENTS:
            errors.append(ThreatModelError("TM-TREATMENT", f"risks.{risk_id}", "risk requires mitigate/avoid/transfer treatment"))
        if risk.get("acceptance") != "pending_human":
            errors.append(ThreatModelError("TM-HUMAN-ACCEPTANCE", f"risks.{risk_id}", "acceptance must remain pending_human"))
        if not str(risk.get("status", "")).startswith("open"):
            errors.append(ThreatModelError("TM-RISK-OPEN", f"risks.{risk_id}", "E0 risks cannot be marked closed"))
        reviewers = risk.get("reviewer_roles")
        if not isinstance(reviewers, list) or not reviewers:
            errors.append(ThreatModelError("TM-REVIEWERS", f"risks.{risk_id}", "independent reviewer role is required"))
        if risk.get("owner_role") in reviewers:
            errors.append(ThreatModelError("TM-INDEPENDENT-REVIEW", f"risks.{risk_id}", "owner cannot be the only reviewer role"))

        evidence = risk.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(ThreatModelError("TM-EVIDENCE", f"risks.{risk_id}", "evidence or planned evidence is required"))
            evidence = []
        for index, item in enumerate(evidence):
            location = f"risks.{risk_id}.evidence.{index}"
            if not isinstance(item, dict) or item.get("status") not in EVIDENCE_STATES:
                errors.append(ThreatModelError("TM-EVIDENCE-STATE", location, "evidence status is invalid"))
                continue
            path = item.get("path")
            if not isinstance(path, str) or not path:
                errors.append(ThreatModelError("TM-EVIDENCE-PATH", location, "evidence path is required"))
            elif repository_root is not None and not (repository_root / path).exists():
                errors.append(ThreatModelError("TM-EVIDENCE-MISSING", location, f"path does not exist: {path}"))

        controls = set(risk.get("controls", []))
        for tag in tags:
            for missing in sorted(SPECIAL_CONTROLS.get(tag, set()) - controls):
                errors.append(ThreatModelError("TM-SCENARIO-CONTROL", f"risks.{risk_id}.controls", f"{tag} requires {missing}"))

    if covered_threats != dfd_threats:
        missing = sorted(dfd_threats - covered_threats)
        errors.append(ThreatModelError("TM-DFD-THREAT-COVERAGE", "risks", f"uncovered DFD threats: {missing}"))
    if covered_flows != dfd_flows:
        missing = sorted(dfd_flows - covered_flows)
        errors.append(ThreatModelError("TM-DFD-FLOW-COVERAGE", "risks", f"uncovered DFD flows: {missing}"))
    if covered_tags != REQUIRED_TAGS:
        missing = sorted(REQUIRED_TAGS - covered_tags)
        errors.append(ThreatModelError("TM-TAG-COVERAGE", "risks", f"uncovered required tags: {missing}"))
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the Fincilia executable threat model")
    parser.add_argument("model", type=Path, nargs="?", default=Path("docs/security/threat-model.json"))
    parser.add_argument("--dfd", type=Path, default=Path("docs/architecture/dfd-flows.json"))
    args = parser.parse_args()
    repository_root = Path.cwd()
    model = json.loads(args.model.read_text(encoding="utf-8"))
    dfd_model = json.loads(args.dfd.read_text(encoding="utf-8"))
    errors = validate_model(model, dfd_model, repository_root)
    print(json.dumps({"errors": [error.as_dict() for error in errors], "ok": not errors}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

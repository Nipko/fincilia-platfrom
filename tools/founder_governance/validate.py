"""Valida owners, independencia y paquete dinámico de decisiones de FNC-GOV-001."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "docs/implementation/founder-governance.json"
CURRENT_PHASE_PATH = ROOT / "CURRENT_PHASE.md"
EXPECTED_ROLES = {
    "Integration Steward": "integration_owner",
    "Product": "product_owner",
    "Accounting": "accounting_owner",
    "Architecture": "architecture_owner",
    "Security": "security_owner",
    "Privacy": "privacy_owner",
    "Legal": "legal_owner",
}
VALID_FOUNDER_STATES = {
    "pending_founder_confirmation",
    "founder_ratified_requires_independent_review",
}


@dataclass(frozen=True)
class GovernanceError:
    code: str
    location: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "location": self.location, "message": self.message}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_source(root: Path, raw: str) -> Path | None:
    candidate = Path(raw)
    if candidate.is_absolute() or ".." in candidate.parts or candidate.is_symlink():
        return None
    resolved_root = root.resolve()
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError:
        return None
    return resolved


def discover_s1_decisions(model: dict[str, Any], root: Path) -> tuple[dict[str, dict[str, Any]], list[GovernanceError]]:
    found: dict[str, dict[str, Any]] = {}
    errors: list[GovernanceError] = []
    for index, raw in enumerate(model.get("decision_sources", [])):
        path = _safe_source(root, raw) if isinstance(raw, str) else None
        location = f"decision_sources[{index}]"
        if path is None:
            errors.append(GovernanceError("GOV-SOURCE-PATH", location, "source must be a repository-relative path without traversal"))
            continue
        if not path.is_file():
            errors.append(GovernanceError("GOV-SOURCE-MISSING", location, f"source does not exist: {raw}"))
            continue
        payload = load_json(path)
        decisions = payload.get("unresolved_decisions", payload.get("open_decisions", []))
        if not isinstance(decisions, list):
            errors.append(GovernanceError("GOV-SOURCE-SHAPE", location, "decision collection must be a list"))
            continue
        for decision in decisions:
            if not isinstance(decision, dict) or "S1-READY" not in decision.get("blocks", []):
                continue
            decision_id = decision.get("id")
            if not isinstance(decision_id, str) or not decision_id:
                errors.append(GovernanceError("GOV-DECISION-ID", location, "S1 decision requires a non-empty id"))
            elif decision_id in found:
                errors.append(GovernanceError("GOV-DECISION-DUPLICATE", decision_id, "decision appears in more than one source"))
            else:
                found[decision_id] = {**decision, "source": raw}
    return found, errors


def _phase_owner(phase: str, field: str) -> str | None:
    prefix = f"{field}:"
    for line in phase.splitlines():
        if line.startswith(prefix):
            return line.split(":", 1)[1].strip()
    return None


def validate(model: dict[str, Any], root: Path = ROOT) -> list[GovernanceError]:
    errors: list[GovernanceError] = []

    principals = model.get("human_principals", [])
    principal_ids = {item.get("id") for item in principals if isinstance(item, dict)}
    if principal_ids != {"FOUNDER-01"} or len(principals) != 1:
        errors.append(GovernanceError("GOV-SINGLE-PRINCIPAL", "human_principals", "exactly FOUNDER-01 must be declared during single-person governance"))

    required = model.get("required_role_slots")
    if set(required or []) != set(EXPECTED_ROLES) or len(required or []) != len(EXPECTED_ROLES):
        errors.append(GovernanceError("GOV-ROLE-SET", "required_role_slots", "all seven required roles must appear exactly once"))

    assignments = model.get("role_assignments", [])
    by_role: dict[str, dict[str, Any]] = {}
    for index, assignment in enumerate(assignments):
        if not isinstance(assignment, dict):
            errors.append(GovernanceError("GOV-ASSIGNMENT-SHAPE", f"role_assignments[{index}]", "assignment must be an object"))
            continue
        role = assignment.get("role")
        if role in by_role:
            errors.append(GovernanceError("GOV-ROLE-DUPLICATE", str(role), "role must be assigned once"))
        elif isinstance(role, str):
            by_role[role] = assignment
    if set(by_role) != set(EXPECTED_ROLES):
        errors.append(GovernanceError("GOV-ASSIGNMENTS", "role_assignments", "assignments must cover the seven required roles"))
    for role, assignment in by_role.items():
        if assignment.get("principal_id") != "FOUNDER-01" or assignment.get("provisional") is not True:
            errors.append(GovernanceError("GOV-FOUNDER-ASSIGNMENT", role, "every role must be provisionally assigned to FOUNDER-01"))

    policy = model.get("single_person_governance", {})
    if policy.get("enabled") is not True or policy.get("founder_direction_state") != "confirmed":
        errors.append(GovernanceError("GOV-DIRECTION", "single_person_governance", "founder direction must be explicitly confirmed"))
    if policy.get("counts_as_independent_review") is not False or policy.get("separation_of_duties_satisfied") is not False:
        errors.append(GovernanceError("GOV-NO-FAKE-INDEPENDENCE", "single_person_governance", "one principal can never count as independent review or satisfied SoD"))
    forbidden = set(policy.get("forbidden_promotions", []))
    for value in ("S1-READY", "DRG-00", "DRG-01", "GA-01", "real_financial_data", "real_pilot", "production_release"):
        if value not in forbidden:
            errors.append(GovernanceError("GOV-FORBIDDEN-PROMOTION", "single_person_governance.forbidden_promotions", f"missing fail-closed promotion: {value}"))

    for index, control in enumerate(model.get("independence_controls", [])):
        location = f"independence_controls[{index}]"
        roles = control.get("required_distinct_roles", []) if isinstance(control, dict) else []
        resolved = {by_role.get(role, {}).get("principal_id") for role in roles}
        if len(roles) < 2 or not set(roles).issubset(by_role):
            errors.append(GovernanceError("GOV-INDEPENDENCE-ROLES", location, "control must cite at least two assigned roles"))
        if len(resolved) == len(roles) or control.get("state") != "unsatisfied_single_principal":
            errors.append(GovernanceError("GOV-INDEPENDENCE-STATE", location, "roles resolving to one founder must remain unsatisfied"))

    phase_path = root / "CURRENT_PHASE.md"
    if not phase_path.is_file():
        errors.append(GovernanceError("GOV-PHASE-MISSING", "CURRENT_PHASE.md", "phase file is required"))
    else:
        phase = phase_path.read_text(encoding="utf-8-sig")
        for _, field in EXPECTED_ROLES.items():
            if _phase_owner(phase, field) != "Founder":
                errors.append(GovernanceError("GOV-PHASE-OWNER", field, "CURRENT_PHASE owner must be Founder"))

    discovered, discovery_errors = discover_s1_decisions(model, root)
    errors.extend(discovery_errors)
    packet = model.get("decision_packet", [])
    packet_by_id = {item.get("id"): item for item in packet if isinstance(item, dict) and isinstance(item.get("id"), str)}
    if len(packet_by_id) != len(packet):
        errors.append(GovernanceError("GOV-PACKET-DUPLICATE", "decision_packet", "packet decisions require unique string ids"))
    if set(packet_by_id) != set(discovered):
        missing = sorted(set(discovered) - set(packet_by_id))
        extra = sorted(set(packet_by_id) - set(discovered))
        errors.append(GovernanceError("GOV-PACKET-COVERAGE", "decision_packet", f"dynamic coverage mismatch; missing={missing}, extra={extra}"))
    for decision_id, source in discovered.items():
        item = packet_by_id.get(decision_id)
        if item is None:
            continue
        if item.get("owner_role") != source.get("owner_role") or item.get("reviewer_roles") != source.get("reviewer_roles"):
            errors.append(GovernanceError("GOV-PACKET-ROLES", decision_id, "owner and reviewer roles must match the source contract"))
        if item.get("founder_state") not in VALID_FOUNDER_STATES:
            errors.append(GovernanceError("GOV-PACKET-STATE", decision_id, "founder state is invalid"))
        if item.get("independent_review_state") != "pending_distinct_human":
            errors.append(GovernanceError("GOV-PACKET-INDEPENDENCE", decision_id, "independent review must remain pending a distinct human"))
        for field in ("recommendation", "consequence", "rollback"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(GovernanceError("GOV-PACKET-EVIDENCE", f"{decision_id}.{field}", "field must be non-empty"))

    gates = model.get("gate_state", {})
    for gate in ("S1-READY", "DRG-00", "DRG-01", "GA-01"):
        if gates.get(gate) != "not_met":
            errors.append(GovernanceError("GOV-GATE-FAIL-CLOSED", f"gate_state.{gate}", "single-person governance cannot promote this gate"))
    return errors


def main() -> int:
    model = load_json(MODEL_PATH)
    errors = validate(model)
    payload = {
        "ok": not errors,
        "errors": [error.as_dict() for error in errors],
        "role_count": len(model.get("role_assignments", [])),
        "human_principal_count": len(model.get("human_principals", [])),
        "decision_count": len(model.get("decision_packet", [])),
        "independent_review_satisfied": False,
        "gate_status": "not_met",
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())

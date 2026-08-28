"""Validador fail-closed para la adjudicación humana de L-01.

El modelo acepta un borrador íntegro o una futura matriz adjudicada con evidencia
humana. Nunca interpreta derecho, inventa plazos ni autoriza datos reales.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any


POLICY_FIELDS = frozenset({
    "policy_id", "decision_state", "retention_days", "legal_basis_ref",
    "contract_ref", "exceptions_ref", "effective_at", "review_evidence_ref",
})
DECISION_FIELDS = (
    "retention_days", "legal_basis_ref", "contract_ref", "exceptions_ref",
    "effective_at", "review_evidence_ref",
)
SIGNOFF_ROLES = frozenset({"Legal", "Privacy", "Security", "Accounting"})
GATE_IDS = frozenset({"L-01", "DRG-00", "DRG-01"})
REFERENCE = re.compile(r"[A-Z0-9][A-Z0-9._:/-]{7,160}")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
FOUNDER_ID = "FOUNDER-01"


@dataclass(frozen=True, order=True)
class Finding:
    code: str
    path: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _finding(code: str, path: str, detail: str) -> Finding:
    return Finding(code, path, detail)


def canonical_digest(value: dict[str, Any]) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _reference(value: Any) -> bool:
    return isinstance(value, str) and REFERENCE.fullmatch(value) is not None


def _source_policies(privacy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    policies = privacy.get("retention_policies")
    if not isinstance(policies, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for item in policies:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            result[item["id"]] = item
    return result


def _validate_source(privacy: dict[str, Any], findings: list[Finding]) -> dict[str, dict[str, Any]]:
    policies = privacy.get("retention_policies")
    if not isinstance(policies, list) or not policies:
        findings.append(_finding(
            "RET-SOURCE-POLICIES", "privacy.retention_policies", "source has no policy inventory"))
        return {}
    identifiers = [item.get("id") for item in policies if isinstance(item, dict)]
    if len(identifiers) != len(policies) or len(set(identifiers)) != len(identifiers):
        findings.append(_finding(
            "RET-SOURCE-IDENTITY", "privacy.retention_policies", "source policy ids are invalid or duplicated"))
    required = {
        "id", "class", "stores", "computation_start", "expiry_trigger",
        "duration_state", "legal_hold", "derived_affected", "purge_method",
        "purge_evidence", "backup_restore_behavior", "owner_role",
        "reviewer_roles", "pending_decision",
    }
    for index, item in enumerate(policies):
        path = f"privacy.retention_policies[{index}]"
        if not isinstance(item, dict) or not required.issubset(item):
            findings.append(_finding("RET-SOURCE-SCHEMA", path, "source policy facts are incomplete"))
            continue
        if item.get("duration_state") not in {"pending_legal", "pending_contract"}:
            findings.append(_finding("RET-SOURCE-DURATION", path, "source must not contain an agent-selected duration"))
        if item.get("pending_decision") not in {"L-01", "L-02"}:
            findings.append(_finding("RET-SOURCE-DECISION", path, "source decision is not recognized"))
        if item.get("legal_hold") != "suspends_purge_and_requires_explicit_documented_basis":
            findings.append(_finding("RET-SOURCE-HOLD", path, "legal hold safety contract drifted"))

    by_id = _source_policies(privacy)
    financial = by_id.get("L-01-FINANCIAL", {})
    if financial.get("computation_start") != "last_related_accounting_entry_or_document":
        findings.append(_finding(
            "RET-FINANCIAL-CLOCK", "privacy.retention_policies.L-01-FINANCIAL",
            "financial clock must start at the last related accounting fact"))
    ledger = by_id.get("L-01-DELETE-LEDGER", {})
    if (ledger.get("backup_restore_behavior") != "outside_ordinary_restore_scope"
            or ledger.get("purge_method") != "retain_beyond_longest_backup_window_then_policy_purge"):
        findings.append(_finding(
            "RET-LEDGER-SOURCE", "privacy.retention_policies.L-01-DELETE-LEDGER",
            "delete ledger must remain outside restore and beyond backup windows"))
    backup = by_id.get("L-01-BACKUP", {})
    if backup.get("stores") != ["backups"]:
        findings.append(_finding(
            "RET-BACKUP-SOURCE", "privacy.retention_policies.L-01-BACKUP",
            "backup policy store contract drifted"))
    deletion = privacy.get("deletion_state_machine")
    if not isinstance(deletion, dict):
        findings.append(_finding("RET-DELETION-SOURCE", "privacy.deletion_state_machine", "state machine missing"))
    else:
        required_path = ["tombstoned", "purge_in_progress", "backup_pending", "reconciled"]
        if (deletion.get("completed_requires_path_through") != required_path
                or deletion.get("restore_requires_tombstone_reapplication_before_service_reopen") is not True
                or deletion.get("legal_hold_silent_activation") is not False
                or deletion.get("ledger_outside_ordinary_restore") is not True
                or deletion.get("ephemeral_export_in_inventory") is not True):
            findings.append(_finding(
                "RET-DELETION-GUARDS", "privacy.deletion_state_machine",
                "source deletion safety invariants drifted"))
    return by_id


def _validate_pending(model: dict[str, Any], findings: list[Finding]) -> None:
    for index, item in enumerate(model.get("policy_decisions", [])):
        if not isinstance(item, dict):
            continue
        if item.get("decision_state") != "pending_human" or any(
                item.get(field) is not None for field in DECISION_FIELDS):
            findings.append(_finding(
                "RET-PREMATURE-DECISION", f"$.policy_decisions[{index}]",
                "draft rows must remain pending with empty human decisions"))
    expected_review = {
        "state": "pending_distinct_reviewers", "legal_reviewer_id": None,
        "competence_ref": None, "decision_ref": None, "approved_at": None,
    }
    if model.get("human_review") != expected_review:
        findings.append(_finding("RET-PREMATURE-REVIEW", "$.human_review", "human review is not pending"))
    for index, item in enumerate(model.get("required_signoffs", [])):
        if (not isinstance(item, dict) or item.get("state") != "pending"
                or item.get("reviewer_id") is not None or item.get("evidence_ref") is not None):
            findings.append(_finding(
                "RET-PREMATURE-SIGNOFF", f"$.required_signoffs[{index}]", "signoff is not pending"))
    for index, item in enumerate(model.get("gate_claims", [])):
        if (not isinstance(item, dict) or item.get("status") != "not_met"
                or item.get("authorized") is not False):
            findings.append(_finding(
                "RET-PREMATURE-GATE", f"$.gate_claims[{index}]", "draft cannot meet a gate"))


def _validate_adjudicated(model: dict[str, Any], findings: list[Finding]) -> None:
    decisions: dict[str, int] = {}
    for index, item in enumerate(model.get("policy_decisions", [])):
        path = f"$.policy_decisions[{index}]"
        if not isinstance(item, dict):
            continue
        days = item.get("retention_days")
        if item.get("decision_state") != "accepted_human":
            findings.append(_finding("RET-ADJUDICATION-STATE", path, "every row needs human acceptance"))
        if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 36500:
            findings.append(_finding("RET-DURATION", path, "retention_days must be an exact bounded integer"))
        else:
            decisions[str(item.get("policy_id"))] = days
        for field in ("legal_basis_ref", "contract_ref", "exceptions_ref", "review_evidence_ref"):
            if not _reference(item.get(field)):
                findings.append(_finding("RET-EVIDENCE", f"{path}.{field}", "stable non-secret evidence ref required"))
        if not isinstance(item.get("effective_at"), str) or DATE.fullmatch(item["effective_at"]) is None:
            findings.append(_finding("RET-EFFECTIVE-DATE", f"{path}.effective_at", "ISO date required"))

    backup_days = decisions.get("L-01-BACKUP")
    ledger_days = decisions.get("L-01-DELETE-LEDGER")
    if backup_days is not None and ledger_days is not None and ledger_days <= backup_days:
        findings.append(_finding(
            "RET-LEDGER-WINDOW", "$.policy_decisions",
            "delete ledger must outlive the longest backup window"))

    review = model.get("human_review")
    if not isinstance(review, dict) or set(review) != {
        "state", "legal_reviewer_id", "competence_ref", "decision_ref", "approved_at",
    }:
        findings.append(_finding("RET-HUMAN-REVIEW", "$.human_review", "human review schema drifted"))
    else:
        reviewer = review.get("legal_reviewer_id")
        if (review.get("state") != "approved_human" or not _reference(reviewer)
                or reviewer == FOUNDER_ID or not _reference(review.get("competence_ref"))
                or not _reference(review.get("decision_ref"))
                or not isinstance(review.get("approved_at"), str)
                or DATE.fullmatch(review["approved_at"]) is None):
            findings.append(_finding(
                "RET-HUMAN-REVIEW", "$.human_review",
                "independent lawyer identity, competence, decision and date are required"))

    reviewer_ids: list[str] = []
    for index, item in enumerate(model.get("required_signoffs", [])):
        path = f"$.required_signoffs[{index}]"
        if not isinstance(item, dict):
            continue
        reviewer = item.get("reviewer_id")
        if (item.get("state") != "approved_human" or not _reference(reviewer)
                or reviewer == FOUNDER_ID or not _reference(item.get("evidence_ref"))):
            findings.append(_finding("RET-SIGNOFF", path, "independent nominal signoff required"))
        elif isinstance(reviewer, str):
            reviewer_ids.append(reviewer)
    if len(reviewer_ids) != len(set(reviewer_ids)):
        findings.append(_finding(
            "RET-SOD", "$.required_signoffs", "signoff reviewers must be distinct"))
    legal_ids = [
        item.get("reviewer_id") for item in model.get("required_signoffs", [])
        if isinstance(item, dict) and item.get("role") == "Legal"
    ]
    if isinstance(review, dict) and legal_ids != [review.get("legal_reviewer_id")]:
        findings.append(_finding(
            "RET-LEGAL-IDENTITY", "$.human_review", "legal signoff must match the reviewing lawyer"))

    expected_claims = {
        "L-01": ("met", True),
        "DRG-00": ("not_met", False),
        "DRG-01": ("not_met", False),
    }
    for index, item in enumerate(model.get("gate_claims", [])):
        if not isinstance(item, dict):
            continue
        if (item.get("status"), item.get("authorized")) != expected_claims.get(item.get("id")):
            findings.append(_finding(
                "RET-GATE-CLAIM", f"$.gate_claims[{index}]",
                "only L-01 may be met; real-data gates remain closed"))


def validate(model: dict[str, Any], privacy: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    top_fields = {
        "schema_version", "task_id", "status", "data_ceiling",
        "real_data_authorized", "source_contract", "decision_contract",
        "policy_decisions", "deletion_guards", "human_review",
        "required_signoffs", "gate_claims",
    }
    if set(model) != top_fields:
        findings.append(_finding("RET-SCHEMA", "$", "top-level contract fields drifted"))
    if model.get("schema_version") != "1.0.0" or model.get("task_id") != "FNC-PRV-002":
        findings.append(_finding("RET-IDENTITY", "$", "unsupported model identity"))
    if model.get("status") not in {"review_pending", "adjudicated"}:
        findings.append(_finding("RET-STATUS", "$.status", "unsupported decision state"))
    if model.get("data_ceiling") != "synthetic_only" or model.get("real_data_authorized") is not False:
        findings.append(_finding("RET-REAL-DATA", "$.data_ceiling", "matrix never authorizes real data"))

    policies = _validate_source(privacy, findings)
    source = model.get("source_contract")
    expected_source = {
        "path": "docs/privacy/privacy-map.json",
        "canonical_sha256": canonical_digest(privacy),
        "selector": "retention_policies[*]",
    }
    if source != expected_source:
        findings.append(_finding("RET-SOURCE-FRESHNESS", "$.source_contract", "privacy-map digest or selector drifted"))

    expected_contract = {
        "duration_unit": "calendar_days", "minimum_days": 1,
        "maximum_days": 36500,
        "clock_start_source": "privacy-map.retention_policies[*].computation_start",
        "policy_facts_source": "privacy-map.retention_policies[*]",
        "adjudication_requires_all_rows": True,
        "partial_adjudication_authorizes_nothing": True,
    }
    if model.get("decision_contract") != expected_contract:
        findings.append(_finding("RET-DECISION-CONTRACT", "$.decision_contract", "adjudication rules drifted"))

    rows = model.get("policy_decisions")
    if not isinstance(rows, list):
        findings.append(_finding("RET-POLICIES", "$.policy_decisions", "policy decisions must be a list"))
        rows = []
    ids = [str(item.get("policy_id")) for item in rows if isinstance(item, dict)]
    if set(ids) != set(policies) or len(ids) != len(policies):
        findings.append(_finding("RET-COVERAGE", "$.policy_decisions", "matrix must exactly cover source policies"))
    for index, item in enumerate(rows):
        if not isinstance(item, dict) or set(item) != POLICY_FIELDS:
            findings.append(_finding(
                "RET-POLICY-SCHEMA", f"$.policy_decisions[{index}]", "policy decision fields drifted"))

    expected_guards = {
        "scope_resolution": "authoritative_per_company_never_from_cache",
        "tombstone_before_active_purge": True,
        "derived_inventory_required": True,
        "ephemeral_exports_in_inventory": True,
        "legal_hold_requires_documented_basis": True,
        "silent_legal_hold_forbidden": True,
        "restore_requires_tombstone_reapplication_before_service_reopen": True,
        "completion_requires_reconciled_inventory": True,
        "delete_ledger_must_exceed_longest_backup_window": True,
    }
    if model.get("deletion_guards") != expected_guards:
        findings.append(_finding("RET-GUARDS", "$.deletion_guards", "deletion safety guards drifted"))

    signoffs = model.get("required_signoffs")
    if not isinstance(signoffs, list):
        findings.append(_finding("RET-SIGNOFFS", "$.required_signoffs", "signoffs must be a list"))
    else:
        roles = [str(item.get("role")) for item in signoffs if isinstance(item, dict)]
        if set(roles) != SIGNOFF_ROLES or len(roles) != len(SIGNOFF_ROLES):
            findings.append(_finding("RET-SIGNOFF-COVERAGE", "$.required_signoffs", "required roles drifted"))
        for index, item in enumerate(signoffs):
            if not isinstance(item, dict) or set(item) != {"role", "reviewer_id", "state", "evidence_ref"}:
                findings.append(_finding("RET-SIGNOFF-SCHEMA", f"$.required_signoffs[{index}]", "signoff fields drifted"))

    claims = model.get("gate_claims")
    if not isinstance(claims, list):
        findings.append(_finding("RET-GATES", "$.gate_claims", "gate claims must be a list"))
    else:
        ids = [str(item.get("id")) for item in claims if isinstance(item, dict)]
        if set(ids) != GATE_IDS or len(ids) != len(GATE_IDS):
            findings.append(_finding("RET-GATE-COVERAGE", "$.gate_claims", "gate inventory drifted"))
        for index, item in enumerate(claims):
            if not isinstance(item, dict) or set(item) != {"id", "status", "authorized"}:
                findings.append(_finding("RET-GATE-SCHEMA", f"$.gate_claims[{index}]", "gate fields drifted"))

    if model.get("status") == "review_pending":
        _validate_pending(model, findings)
    elif model.get("status") == "adjudicated":
        _validate_adjudicated(model, findings)
    return sorted(set(findings))


def report(model: dict[str, Any], privacy: dict[str, Any]) -> dict[str, Any]:
    findings = validate(model, privacy)
    rows = model.get("policy_decisions") if isinstance(model.get("policy_decisions"), list) else []
    accepted = [item for item in rows if isinstance(item, dict) and item.get("decision_state") == "accepted_human"]
    pending = [item for item in rows if isinstance(item, dict) and item.get("decision_state") == "pending_human"]
    decisions = {
        item.get("policy_id"): item.get("retention_days") for item in rows
        if isinstance(item, dict) and isinstance(item.get("retention_days"), int)
        and not isinstance(item.get("retention_days"), bool)
    }
    return {
        "ok": not findings,
        "model_valid": not findings,
        "decision_state": model.get("status"),
        "source_fresh": isinstance(model.get("source_contract"), dict)
        and model["source_contract"].get("canonical_sha256") == canonical_digest(privacy),
        "policy_count": len(_source_policies(privacy)),
        "pending_policy_count": len(pending),
        "accepted_policy_count": len(accepted),
        "human_adjudication": model.get("status") == "adjudicated" and not findings,
        "l01_met": model.get("status") == "adjudicated" and not findings,
        "real_data_authorized": False,
        "drg00_met": False,
        "drg01_met": False,
        "backup_days": decisions.get("L-01-BACKUP"),
        "delete_ledger_days": decisions.get("L-01-DELETE-LEDGER"),
        "aggregate_score": None,
        "findings": [item.as_dict() for item in findings],
    }

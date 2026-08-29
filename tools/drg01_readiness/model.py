from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "docs/security/drg01-readiness.json"
FOUNDER_ID = "FOUNDER-01"
GATE_ORDER = ("DRG-00", "DRG-01")
CONTROL_IDS = {
    "DRG-00": {
        "G00-LEGAL", "G00-RETENTION", "G00-REGION", "G00-ISOLATED-ENV",
        "G00-INVENTORY", "G00-DELETE", "G00-DRILL",
        "G00-INDEPENDENT-REVIEW",
    },
    "DRG-01": {
        "D01-DRG00", "D01-IDENTITY", "D01-XTENANT", "D01-INGRESS",
        "D01-CHANNELS", "D01-CLOUD-CONTROLS", "D01-RESTORE", "D01-PCI",
        "D01-RIGHTS-IR", "D01-PENTEST", "D01-DPA-SUBPROCESSORS",
        "D01-SUPPLY-CHAIN", "D01-INDEPENDENT-REVIEW",
    },
}
HUMAN_IDS = {
    "G00-LEGAL", "G00-RETENTION", "G00-REGION", "G00-INDEPENDENT-REVIEW",
    "D01-PCI", "D01-PENTEST", "D01-DPA-SUBPROCESSORS",
    "D01-INDEPENDENT-REVIEW",
}
PREREQUISITE_IDS = {"D01-DRG00"}
ALLOWED_DOCUMENTS = ["csv", "xlsx", "pdf"]
DRG00_TECHNICAL_EVIDENCE = "docs/implementation/evidence/FNC-QA-001.json"
DRG00_TECHNICAL_IDS = {
    "G00-ISOLATED-ENV", "G00-INVENTORY", "G00-DELETE", "G00-DRILL",
}
PROHIBITED_DATA = [
    "payment_card", "payroll", "government_identity", "health", "credentials",
]
DISABLED_CAPABILITIES = [
    "external_ai", "email_ingest", "sftp", "api_connectors", "webhooks",
    "automatic_close",
]


@dataclass(frozen=True, order=True)
class Finding:
    code: str
    subject: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _inside_evidence(reference: str) -> bool:
    path = Path(reference)
    if path.is_absolute() or ".." in path.parts:
        return False
    try:
        (ROOT / path).resolve().relative_to(ROOT.resolve())
    except ValueError:
        return False
    return (ROOT / path).exists()


def _control_satisfied(control: dict[str, Any], drg00_ready: bool) -> bool:
    kind = control.get("kind")
    if kind == "human":
        return (
            control.get("state") == "accepted"
            and bool(control.get("evidence_refs"))
            and control.get("reviewer_id") not in {None, "", FOUNDER_ID}
            and bool(control.get("reviewed_at"))
        )
    if kind == "automated":
        return control.get("state") == "passed" and bool(control.get("evidence_refs"))
    if kind == "prerequisite":
        return control.get("state") == "passed" and drg00_ready
    return False


def _validate_drg00_technical_evidence() -> list[Finding]:
    path = ROOT / DRG00_TECHNICAL_EVIDENCE
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return [Finding("DRG-TECH-EVIDENCE", DRG00_TECHNICAL_EVIDENCE,
                        "technical evidence is absent or unreadable")]
    findings: list[Finding] = []
    expected_tests = [f"LAB-T{number:02d}" for number in range(1, 13)]
    tests = payload.get("tests") if isinstance(payload, dict) else None
    mappings = payload.get("technical_controls") if isinstance(payload, dict) else None
    if (
        payload.get("schema_version") != "1.0.0"
        or payload.get("task_id") != "FNC-QA-001"
        or payload.get("data_classification") != "completely_synthetic"
        or payload.get("real_data_authorized") is not False
        or payload.get("test_count") != 12
        or payload.get("passed_count") != 12
        or payload.get("failed_count") != 0
        or not isinstance(tests, list)
        or [item.get("id") for item in tests if isinstance(item, dict)] != expected_tests
        or any(item.get("state") != "passed" for item in tests if isinstance(item, dict))
        or not isinstance(mappings, dict)
        or set(mappings) != DRG00_TECHNICAL_IDS
        or any(not value for value in mappings.values())
    ):
        findings.append(Finding(
            "DRG-TECH-EVIDENCE", DRG00_TECHNICAL_EVIDENCE,
            "technical evidence does not prove the four mapped controls"))
    claimed = payload.get("evidence_sha256")
    unsigned = {key: value for key, value in payload.items() if key != "evidence_sha256"}
    observed = hashlib.sha256(json.dumps(
        unsigned, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    if claimed != observed:
        findings.append(Finding(
            "DRG-TECH-DIGEST", DRG00_TECHNICAL_EVIDENCE,
            "technical evidence digest does not match its content"))
    return findings


def validate(model: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    required = {
        "schema_version", "task_id", "status", "target", "data_ceiling",
        "real_data_authorized", "pilot_scope", "selected_architecture",
        "controls", "gate_claims", "human_acceptance",
        "founder_is_independent_reviewer",
    }
    if set(model) != required:
        findings.append(Finding("DRG-SCHEMA", "$", "top-level fields drifted"))
    if model.get("schema_version") != "1.0.0" or model.get("task_id") != "FNC-GAT-005":
        findings.append(Finding("DRG-IDENTITY", "$", "unsupported model identity"))
    if model.get("founder_is_independent_reviewer") is not False:
        findings.append(Finding("DRG-SOD", "founder", "Founder cannot be the independent reviewer"))

    scope = model.get("pilot_scope", {})
    if (
        scope.get("operator_mode") != "founder_first_named_users_only"
        or not isinstance(scope.get("maximum_companies"), int)
        or scope.get("maximum_companies") != 1
        or not isinstance(scope.get("maximum_users"), int)
        or not 1 <= scope.get("maximum_users", 0) <= 3
        or scope.get("allowed_document_types") != ALLOWED_DOCUMENTS
        or scope.get("prohibited_data_categories") != PROHIBITED_DATA
        or scope.get("disabled_capabilities") != DISABLED_CAPABILITIES
        or scope.get("invite_only") is not True
    ):
        findings.append(Finding("DRG-SCOPE", "pilot_scope", "first real pilot scope was widened"))

    architecture = model.get("selected_architecture", {})
    expected_architecture = {
        "provider": "AWS",
        "primary_region": "sa-east-1",
        "selection_state": "founder_direction_pending_independent_review",
        "public_web_entry": "https_only_with_waf",
        "data_stores": "private_subnets_and_customer_managed_kms",
        "management": "ssm_only_no_ssh",
        "external_ai": "disabled",
    }
    if architecture != expected_architecture:
        findings.append(Finding("DRG-ARCHITECTURE", "selected_architecture", "pilot architecture drifted"))

    controls = model.get("controls")
    if not isinstance(controls, list):
        controls = []
        findings.append(Finding("DRG-CONTROLS", "controls", "controls must be a list"))
    by_id = {item.get("id"): item for item in controls if isinstance(item, dict)}
    expected_ids = set().union(*CONTROL_IDS.values())
    if set(by_id) != expected_ids or len(controls) != len(expected_ids):
        findings.append(Finding("DRG-COVERAGE", "controls", "required control set drifted"))

    exact_fields = {
        "id", "gate", "domain", "kind", "owner_role", "reviewer_roles",
        "state", "evidence_refs", "reviewer_id", "reviewed_at",
    }
    for identifier, control in by_id.items():
        if set(control) != exact_fields:
            findings.append(Finding("DRG-CONTROL-SCHEMA", str(identifier), "control fields drifted"))
            continue
        gate = control.get("gate")
        if gate not in CONTROL_IDS or identifier not in CONTROL_IDS[gate]:
            findings.append(Finding("DRG-CONTROL-GATE", str(identifier), "control assigned to wrong gate"))
        expected_kind = "human" if identifier in HUMAN_IDS else (
            "prerequisite" if identifier in PREREQUISITE_IDS else "automated")
        if control.get("kind") != expected_kind:
            findings.append(Finding("DRG-CONTROL-KIND", str(identifier), "control kind drifted"))
        if not control.get("owner_role") or not control.get("reviewer_roles"):
            findings.append(Finding("DRG-CONTROL-OWNER", str(identifier), "owner or reviewer role missing"))
        refs = control.get("evidence_refs")
        if not isinstance(refs, list) or len(refs) != len(set(refs)):
            findings.append(Finding("DRG-EVIDENCE", str(identifier), "evidence refs must be a unique list"))
            refs = []
        for reference in refs:
            if not isinstance(reference, str) or not _inside_evidence(reference):
                findings.append(Finding("DRG-EVIDENCE", str(identifier), f"invalid evidence {reference!r}"))
        if control.get("state") in {"accepted", "passed"} and not refs:
            findings.append(Finding("DRG-EVIDENCE", str(identifier), "completed control needs reproducible evidence"))
        if control.get("state") == "pending" and (
            refs or control.get("reviewer_id") is not None or control.get("reviewed_at") is not None
        ):
            findings.append(Finding("DRG-PREMATURE-EVIDENCE", str(identifier), "pending control claims evidence or review"))
        if control.get("kind") == "human" and control.get("state") not in {"pending", "accepted"}:
            findings.append(Finding("DRG-HUMAN-STATE", str(identifier), "human control state is invalid"))
        if control.get("kind") in {"automated", "prerequisite"} and control.get("state") not in {"pending", "passed"}:
            findings.append(Finding("DRG-AUTO-STATE", str(identifier), "technical control state is invalid"))
        if control.get("state") == "accepted" and control.get("reviewer_id") == FOUNDER_ID:
            findings.append(Finding("DRG-SOD", str(identifier), "Founder cannot independently review the control"))
        if identifier in DRG00_TECHNICAL_IDS and control.get("state") == "passed":
            if control.get("evidence_refs") != [DRG00_TECHNICAL_EVIDENCE]:
                findings.append(Finding(
                    "DRG-TECH-REF", str(identifier),
                    "DRG-00 technical controls require the adjudicated drill evidence"))

    if any(by_id.get(identifier, {}).get("state") == "passed"
           for identifier in DRG00_TECHNICAL_IDS):
        findings.extend(_validate_drg00_technical_evidence())

    drg00_ready = all(
        _control_satisfied(by_id.get(identifier, {}), False)
        for identifier in CONTROL_IDS["DRG-00"]
    )
    drg01_ready = drg00_ready and all(
        _control_satisfied(by_id.get(identifier, {}), drg00_ready)
        for identifier in CONTROL_IDS["DRG-01"]
    )
    claims = model.get("gate_claims")
    expected_claims = [
        {"id": "DRG-00", "status": "met" if drg00_ready else "not_met", "authorized": drg00_ready},
        {"id": "DRG-01", "status": "met" if drg01_ready else "not_met", "authorized": drg01_ready},
    ]
    if claims != expected_claims:
        findings.append(Finding("DRG-GATE-DERIVATION", "gate_claims", "gate claims do not match evidence"))
    expected_ceiling = "pilot_real_data" if drg01_ready else (
        "real_corpus_only" if drg00_ready else "synthetic_only")
    if model.get("data_ceiling") != expected_ceiling or model.get("real_data_authorized") is not drg01_ready:
        findings.append(Finding("DRG-DATA-DERIVATION", "data_ceiling", "data authorization does not match gates"))
    if model.get("human_acceptance") != (
        "accepted" if drg01_ready else "pending_independent_review"
    ):
        findings.append(Finding("DRG-HUMAN-DERIVATION", "human_acceptance", "human acceptance does not match gate"))
    return sorted(set(findings))


def report(model: dict[str, Any]) -> dict[str, Any]:
    findings = validate(model)
    controls = model.get("controls", []) if isinstance(model.get("controls"), list) else []
    blockers = [
        {"id": item.get("id"), "gate": item.get("gate"), "owner_role": item.get("owner_role"), "kind": item.get("kind")}
        for item in controls if item.get("state") == "pending"
    ]
    return {
        "ok": not findings,
        "model_valid": not findings,
        "real_data_authorized": model.get("real_data_authorized") is True and not findings,
        "gates": model.get("gate_claims", []),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "findings": [item.as_dict() for item in findings],
    }


def load_model() -> dict[str, Any]:
    return json.loads(MODEL_PATH.read_text(encoding="utf-8"))

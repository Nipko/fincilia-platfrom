from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = Path("docs/architecture/adr-readiness.json")
ADR_ID = re.compile(r"^ADR-\d{3}$")


@dataclass(frozen=True)
class Finding:
    code: str
    subject: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "subject": self.subject, "detail": self.detail}


def _inside(root: Path, relative: str) -> Path | None:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        return None
    resolved_root = root.resolve()
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError:
        return None
    return resolved


def discover_adrs(root: Path) -> dict[str, str]:
    found: dict[str, str] = {}
    for path in sorted((root / "docs/adr").glob("ADR-[0-9][0-9][0-9]-*.md")):
        match = re.match(r"(ADR-\d{3})-", path.name)
        if match and match.group(1) != "ADR-000":
            found[match.group(1)] = path.relative_to(root).as_posix()
    return found


def _metadata(text: str, label: str) -> str | None:
    match = re.search(rf"^- (?:{label}):\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip() if match else None


def validate_model(model: dict[str, Any], root: Path = ROOT) -> list[Finding]:
    findings: list[Finding] = []
    required_top = {
        "schema_version", "task", "status", "data_ceiling", "human_acceptance",
        "agent_may_accept", "required_s1_adrs", "allowed_readiness", "release_rule",
        "adrs", "decisions",
    }
    unknown = set(model) - required_top
    missing = required_top - set(model)
    if missing:
        findings.append(Finding("ADR-RDY-SCHEMA", "model", f"missing {sorted(missing)}"))
    if unknown:
        findings.append(Finding("ADR-RDY-SCHEMA", "model", f"unknown {sorted(unknown)}"))
    if missing:
        return findings

    if model["data_ceiling"] != "synthetic_only":
        findings.append(Finding("ADR-RDY-DATA", "model", "data ceiling must remain synthetic_only"))
    if model["human_acceptance"] != "pending" or model["agent_may_accept"] is not False:
        findings.append(Finding("ADR-RDY-HUMAN", "model", "agent cannot accept decisions"))

    release = model["release_rule"]
    if release.get("state") != "not_met" or release.get("gate") != "S1-READY":
        findings.append(Finding("ADR-RDY-GATE", "release_rule", "S1-READY must remain not_met"))
    for key in ("requires_no_blocked_core", "requires_assigned_human_owners", "requires_independent_reviews", "requires_evidence_refs"):
        if release.get(key) is not True:
            findings.append(Finding("ADR-RDY-GATE", key, "required gate control disabled"))

    discovered = discover_adrs(root)
    records = model["adrs"]
    ids = [record.get("id") for record in records]
    if len(ids) != len(set(ids)):
        findings.append(Finding("ADR-RDY-DUPLICATE", "adrs", "duplicate ADR id"))
    registered = set(ids)
    if registered != set(discovered):
        findings.append(Finding("ADR-RDY-COVERAGE", "adrs", f"registered={sorted(registered)} discovered={sorted(discovered)}"))
    required = set(model["required_s1_adrs"])
    expected_core = {f"ADR-{number:03d}" for number in range(1, 11)} | {"ADR-023"}
    if required != expected_core:
        findings.append(Finding("ADR-RDY-CORE", "required_s1_adrs", "core ADR set changed"))

    allowed = set(model["allowed_readiness"])
    for record in records:
        identifier = record.get("id", "<missing>")
        expected_keys = {"id", "path", "readiness", "scope", "owners", "reviewers", "evidence", "blockers"}
        if set(record) != expected_keys:
            findings.append(Finding("ADR-RDY-RECORD", identifier, "record keys must be exact"))
            continue
        if not ADR_ID.fullmatch(identifier):
            findings.append(Finding("ADR-RDY-ID", identifier, "invalid ADR id"))
        if record["readiness"] not in allowed:
            findings.append(Finding("ADR-RDY-STATE", identifier, "unknown readiness"))
        if not record["owners"] or not record["reviewers"] or set(record["owners"]) & set(record["reviewers"]):
            findings.append(Finding("ADR-RDY-SOD", identifier, "owners/reviewers missing or overlapping"))
        if not record["evidence"]:
            findings.append(Finding("ADR-RDY-EVIDENCE", identifier, "evidence required"))
        if record["readiness"] not in {"documented", "ready"} and not record["blockers"]:
            findings.append(Finding("ADR-RDY-BLOCKER", identifier, "conditional/blocked ADR needs blockers"))

        path = _inside(root, record["path"])
        if path is None or not path.is_file() or discovered.get(identifier) != record["path"]:
            findings.append(Finding("ADR-RDY-PATH", identifier, record["path"]))
            continue
        text = path.read_text(encoding="utf-8")
        if not text.startswith(f"# {identifier}"):
            findings.append(Finding("ADR-RDY-TITLE", identifier, "title/id mismatch"))
        status = _metadata(text, "Status|Estado")
        if not status:
            findings.append(Finding("ADR-RDY-METADATA", identifier, "status missing"))
        elif "proposed" in status.lower() and record["readiness"] != "blocked":
            findings.append(Finding("ADR-RDY-PROPOSED", identifier, "Proposed ADR must be blocked"))
        if "UNASSIGNED" in text and "named_owner_assignment" not in record["blockers"]:
            findings.append(Finding("ADR-RDY-OWNER", identifier, "unassigned owner not represented as blocker"))
        for evidence in record["evidence"]:
            evidence_path = _inside(root, evidence)
            if evidence_path is None or not evidence_path.exists():
                findings.append(Finding("ADR-RDY-EVIDENCE", identifier, evidence))

    for decision in model["decisions"]:
        if set(decision) != {"id", "state", "owner", "question", "blocks"}:
            findings.append(Finding("ADR-RDY-DECISION", str(decision.get("id")), "decision keys must be exact"))
        if decision.get("state") != "pending_human" or not decision.get("owner") or not decision.get("question") or decision.get("blocks") != ["S1-READY"]:
            findings.append(Finding("ADR-RDY-DECISION", str(decision.get("id")), "decision must remain pending_human"))

    return findings


def validate_repository(root: Path = ROOT, model_override: dict[str, Any] | None = None) -> tuple[dict[str, Any], list[Finding]]:
    model = model_override or json.loads((root / MODEL_PATH).read_text(encoding="utf-8"))
    findings = validate_model(model, root)
    report = {
        "adr_count": len(model.get("adrs", [])),
        "core_count": len(model.get("required_s1_adrs", [])),
        "blocked": sorted(record["id"] for record in model.get("adrs", []) if record.get("readiness") == "blocked"),
        "conditional": sorted(record["id"] for record in model.get("adrs", []) if record.get("readiness") == "conditional"),
        "gate": model.get("release_rule", {}).get("state"),
    }
    return report, findings


def main() -> int:
    report, findings = validate_repository()
    print(json.dumps({"ok": not findings, "report": report, "errors": [finding.as_dict() for finding in findings]}, indent=2, sort_keys=True))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
